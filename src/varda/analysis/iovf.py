"""Iterative Outlier Voting Filter (IOVF; Phillips et al. 2024, Icarus 419).

Removes isolated spikes from a (rows, cols, bands) cube without smoothing the
spectra around them:

1. Reference spectrum per pixel: a 19-band running median, then a
   Savitzky-Golay smooth. ``noise = cube - reference``.
2. Election: a two-sided Smirnov-Grubbs test runs on every window (7x5x5 by
   default) of the noise cube (alpha 0.125, or 0.05 for edge windows truncated
   below 45 voxels). Every voxel a window flags gets one vote.
3. Voxels with at least ``min(window)`` votes are replaced by the
   Gaussian-weighted average of their unflagged neighbors.
4. Later rounds re-run the election only around the voxels replaced in the
   previous round, until nothing is flagged or the vote counts cycle.
5. The result is reference + cleaned noise.

Ported from the vectorized ``iovf_fast.py`` (PTYS 551 lab code), without its
mode that reproduces the original ``iovf_generic`` round-off for round-off.
One change: NaN voxels (no-data) are left out of the windows instead of
counting as zero noise, so a scene's no-data border is not mistaken for
outliers. Cubes without NaN filter exactly as with ``iovf_fast``.
Windows are strided views of one padded cube tested in small batches; a cheap
screen built from separable box statistics skips windows that cannot contain
an outlier; row blocks run on a thread pool (numpy releases the GIL).
"""

from __future__ import annotations

import os
import threading
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import attrs
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy import ndimage, signal, stats

# (percent 0-100, message)
ProgressCallback = Callable[[int, str], None]

DEFAULT_WINDOW = (7, 5, 5)
DEFAULT_STOP_FRACTION = 0.01
_SMALL_WINDOW_VOLUME = 45  # edge windows below this use the stricter alpha
_ALPHA_SMALL = 0.05
_ALPHA_LARGE = 0.125
_REFERENCE_MEDIAN_BANDS = 19


@attrs.frozen
class IovfResult:
    filtered: np.ndarray  # float64 (rows, cols, bands)
    replaced: list[int]  # voxels replaced in each round
    reference: np.ndarray  # the smooth reference cube

    @property
    def rounds(self) -> int:
        return len(self.replaced)


def iovfFilter(
    cube: np.ndarray,
    window: tuple[int, int, int] = DEFAULT_WINDOW,
    *,
    nJobs: int | None = None,
    batchMb: float = 4.0,
    maxRounds: int = 200,
    stopFraction: float = DEFAULT_STOP_FRACTION,
    progress: ProgressCallback | None = None,
) -> IovfResult:
    """Filter ``cube`` (rows, cols, bands). NaN voxels (no-data) are left out.

    Rounds continue until none is flagged, the counts cycle, ``maxRounds``,
    or a round replaces fewer than ``stopFraction`` of the first round's
    voxels (0 runs to convergence, as the original does; the long tail of
    small rounds changes very little)."""
    report = progress or (lambda percent, message: None)
    if len(window) != 3 or any(int(w) % 2 == 0 or int(w) < 1 for w in window):
        raise ValueError("window sizes must be three odd numbers")
    window = (int(window[0]), int(window[1]), int(window[2]))
    data = np.asarray(cube, dtype=np.float64)
    if any(data.shape[d] < window[d] for d in range(3)):
        raise ValueError(f"cube {data.shape} is smaller than the window {window}")
    jobs = min(8, os.cpu_count() or 1) if nJobs is None else max(1, int(nJobs))

    report(0, "building the reference spectra")
    reference, noise = _centerData(data, jobs)
    filt = _Election(window, jobs, batchMb)

    half = tuple(w // 2 for w in window)
    shape = noise.shape
    voteThreshold = min(window)
    replaced: list[int] = []
    flagged: np.ndarray | None = None
    while len(replaced) < maxRounds:
        round_ = len(replaced) + 1
        padded = _pad(noise, half)
        if flagged is None:
            votes = filt.run(padded, None, shape)
        else:
            previous = np.zeros(shape, dtype=np.uint8)
            previous[tuple(flagged.T)] = 1
            centers = ndimage.maximum_filter(previous, size=window, mode="constant") > 0
            votes = filt.run(padded, centers, shape)
        flagged = np.argwhere(votes >= voteThreshold)
        replaced.append(int(flagged.shape[0]))
        if flagged.shape[0]:
            _replace(noise, padded, flagged, window, half, filt.kernels, batchMb)
        # rounds shrink geometrically; report against a nominal 12-round run
        report(
            min(95, 5 + 90 * round_ // 12),
            f"round {round_}: {flagged.shape[0]} voxels replaced",
        )
        if flagged.shape[0] == 0 or _isCycling(replaced):
            break
        if stopFraction > 0 and round_ > 1:
            if flagged.shape[0] < stopFraction * replaced[0] or _isStalled(replaced):
                break
    report(100, "done")
    return IovfResult(
        filtered=noise + reference, replaced=replaced, reference=reference
    )


def _isStalled(replaced: list[int], rounds: int = 5) -> bool:
    """True when the last ``rounds`` rounds replaced no fewer voxels, overall,
    than the round before them (the filter has stopped making progress)."""
    return len(replaced) > rounds and replaced[-1] >= replaced[-1 - rounds]


def _isCycling(replaced: list[int]) -> bool:
    """True once the round-to-round change in replaced voxels repeats with a
    period of 4 to 7 rounds (the vote counts are oscillating, not converging)."""
    if len(replaced) < 14:
        return False
    d = np.diff(replaced).tolist()
    return any(d[-2 * p : -p] == d[-p:] for p in (4, 5, 6, 7))


# --- reference / noise ---------------------------------------------------------


def _centerData(cube: np.ndarray, jobs: int) -> tuple[np.ndarray, np.ndarray]:
    """Running median (19 bands) then Savitzky-Golay along the bands, in row
    blocks. The band axis is padded by mirroring at the start and repeating
    the end, as the original implementation does."""
    rows, cols, nb = cube.shape
    size = _REFERENCE_MEDIAN_BANDS
    pad = int(np.ceil(size / 2))
    sgWindow = pad - 1 if pad % 2 == 0 else pad
    idx = np.concatenate(
        [np.arange(pad, 0, -1), np.arange(nb), np.arange(nb - 1, nb - 1 - pad, -1)]
    )
    idx = np.clip(idx, 0, nb - 1)
    reference = np.empty((rows, cols, nb))
    noise = np.empty((rows, cols, nb))
    step = max(1, int(1e6 // (cols * (nb + 2 * pad))))

    def block(i0: int) -> None:
        blk = cube[i0 : i0 + step]
        med = ndimage.median_filter(blk[:, :, idx], size=(1, 1, size), mode="constant")
        polyorder = min(3, sgWindow - 1)
        ref = signal.savgol_filter(
            med[:, :, pad : pad + nb], sgWindow, polyorder, mode="mirror", axis=2
        )
        reference[i0 : i0 + step] = ref
        np.subtract(blk, ref, out=noise[i0 : i0 + step])

    _forEach(block, range(0, rows, step), jobs)
    return reference, noise


def _forEach(fn: Callable[[int], None], starts: range, jobs: int) -> None:
    if jobs <= 1:
        for start in starts:
            fn(start)
        return
    with ThreadPoolExecutor(jobs) as executor:
        list(executor.map(fn, starts))


# --- Grubbs test ---------------------------------------------------------------


def _grubbsCritical(nmax: int, alpha: float) -> np.ndarray:
    """Two-sided Grubbs critical values G[n] for n = 0..nmax (inf for n <= 2,
    where the test is undefined)."""
    g = np.full(nmax + 1, np.inf)
    if nmax >= 3:
        n = np.arange(3, nmax + 1, dtype=np.float64)
        t = stats.t.isf(alpha / (2 * n), n - 2)
        g[3:] = ((n - 1) / np.sqrt(n)) * np.sqrt(t**2 / (n - 2 + t**2))
    return g


def _workspace(n: int, m: int) -> dict[str, np.ndarray]:
    return {
        "D": np.empty((n, m)),
        "R": np.empty((n, m)),
        "E": np.empty((n, m), dtype=bool),
    }


def _grubbsBatch(
    X: np.ndarray,
    outside: np.ndarray | None,
    gSmall: np.ndarray,
    gLarge: np.ndarray,
    ws: dict[str, np.ndarray],
) -> np.ndarray:
    """Iterative two-sided Grubbs test on every row of ``X`` (one window per
    row; 0 where ``outside``, members zeroed in place as they are flagged).
    Returns bool (n, m): True where a member was flagged.

    Members outside the image or already removed are held at zero deviation,
    so they drop out of the sums and never win the argmax. If a window's
    remaining members become identical the test stops and keeps what it found.
    """
    n, m = X.shape
    vol = np.full(n, m, dtype=np.intp) if outside is None else m - outside.sum(axis=1)
    small = vol < _SMALL_WINDOW_VOLUME
    flagged = np.zeros((n, m), dtype=bool)
    excluded = flagged if outside is None else outside.copy()
    count = vol.copy()

    idx = np.arange(n)
    Xr, Er = X, outside
    while idx.size:
        nr = idx.size
        c = count[idx]
        with np.errstate(divide="ignore", invalid="ignore"):
            mean = Xr.sum(axis=1) / c
        d = ws["D"][:nr]
        np.subtract(Xr, mean[:, None], out=d)
        if Er is not None:
            np.copyto(d, 0.0, where=Er)
        with np.errstate(divide="ignore", invalid="ignore"):
            std = np.sqrt(np.einsum("ij,ij->i", d, d) / c)
        np.abs(d, out=d)
        k = d.argmax(axis=1)
        val = d[np.arange(nr), k]
        G = np.where(small[idx], gSmall[c], gLarge[c])
        with np.errstate(divide="ignore", invalid="ignore"):
            hit = (val / std > G) & (std != 0.0)
        idx, k = idx[hit], k[hit]
        flagged[idx, k] = True
        if excluded is not flagged:
            excluded[idx, k] = True
        X[idx, k] = 0.0
        count[idx] -= 1
        if idx.size:
            nr = idx.size
            Xr = np.take(X, idx, axis=0, out=ws["R"][:nr])
            Er = np.take(excluded, idx, axis=0, out=ws["E"][:nr])

    flagged[flagged.sum(axis=1) == vol] = False  # every member flagged: ignore
    return flagged


# --- election --------------------------------------------------------------------


def _pad(noise: np.ndarray, half: tuple[int, ...]) -> np.ndarray:
    """``noise`` padded with NaN by ``half`` on every side. NaN marks voxels
    left out of the windows: outside the image, or no-data inside it (as zero
    noise, a no-data border would make every voxel along it an outlier)."""
    shape = tuple(noise.shape[d] + 2 * half[d] for d in range(3))
    padded = np.full(shape, np.nan)
    inner = padded[
        half[0] : half[0] + noise.shape[0],
        half[1] : half[1] + noise.shape[1],
        half[2] : half[2] + noise.shape[2],
    ]
    np.copyto(inner, noise)
    return padded


def _box(a: np.ndarray, window: tuple[int, ...], op) -> np.ndarray:
    """Separable 'valid' box reduction: out[p] = op over the window at p.
    ``op`` is np.add, np.maximum or np.minimum."""
    for ax in (2, 1, 0):
        w = window[ax]
        length = a.shape[ax] - w + 1
        sl: list[slice] = [slice(None)] * 3
        sl[ax] = slice(0, length)
        out = a[tuple(sl)].copy()
        for k in range(1, w):
            sl[ax] = slice(k, k + length)
            op(out, a[tuple(sl)], out=out)
        a = out
    return a


def _batchRows(m: int, batchMb: float) -> int:
    return max(1, int(batchMb * 2**20 // (8 * m)))


class _Election:
    def __init__(self, window: tuple[int, ...], jobs: int, batchMb: float) -> None:
        self.window = window
        self.jobs = jobs
        self.batchMb = batchMb
        m = int(np.prod(window))
        self.gSmall = _grubbsCritical(m, _ALPHA_SMALL)
        self.gLarge = _grubbsCritical(m, _ALPHA_LARGE)
        self.kernels = _kernelTables(window)

    def _screen(self, P: np.ndarray, i0: int, i1: int, ncent: tuple[int, ...]):
        """The first Grubbs iteration for every window centered in rows i0..i1-1,
        from box statistics. True where the window might hold an outlier; a
        window that fails the first iteration casts no votes, so only these
        need the full iterative test. The margin keeps the screen conservative."""
        w0, w1, w2 = self.window
        blk = P[i0 : i1 + w0 - 1, : ncent[1] + w1 - 1, : ncent[2] + w2 - 1]
        inside = ~np.isnan(blk)
        x = np.where(inside, blk, 0.0)
        N = _box(inside.astype(np.float64), self.window, np.add)
        S1 = _box(x, self.window, np.add)
        S2 = _box(x * x, self.window, np.add)
        MX = _box(np.where(inside, blk, -np.inf), self.window, np.maximum)
        MN = _box(np.where(inside, blk, np.inf), self.window, np.minimum)
        n = np.rint(N).astype(np.intp)
        G = np.where(n < _SMALL_WINDOW_VOLUME, self.gSmall[n], self.gLarge[n])
        with np.errstate(divide="ignore", invalid="ignore"):
            mean = S1 / N
            var = S2 / N - mean * mean
            g = np.maximum(MX - mean, mean - MN) / np.sqrt(var)
            candidate = ~(g <= G * (1.0 - 1e-6))  # NaN (var <= 0) -> candidate
            candidate |= mean * mean > 1e6 * var
        return candidate

    def run(
        self, P: np.ndarray, centers: np.ndarray | None, shape: tuple[int, ...]
    ) -> np.ndarray:
        """Votes (``shape``) from the Grubbs test on every window whose center is
        True in ``centers`` (None: every voxel). ``P`` is the padded noise cube."""
        window = self.window
        half = tuple(w // 2 for w in window)
        m = int(np.prod(window))
        S = P.shape
        ncent = shape
        st0, st1 = S[1] * S[2], S[2]
        k0, k1, k2 = np.meshgrid(*(np.arange(w) for w in window), indexing="ij")
        offsets = (k0 * st0 + k1 * st1 + k2).ravel()
        V = sliding_window_view(P, window)
        votes = np.zeros(S, dtype=np.uint8 if m <= 255 else np.uint16)
        flatVotes = votes.reshape(-1)
        nwin = _batchRows(m, self.batchMb)
        rowStep = max(1, int(4e5 // (ncent[1] * ncent[2])))
        local = threading.local()

        def work(i0: int) -> np.ndarray:
            i1 = min(i0 + rowStep, ncent[0])
            if centers is None:
                candidate = self._screen(P, i0, i1, ncent)
            else:
                chunk = centers[i0:i1]
                count = np.count_nonzero(chunk)
                if count == 0:
                    return np.empty(0, dtype=np.intp)
                if count < 0.2 * chunk.size:  # sparse: screening isn't worth it
                    candidate = chunk
                else:
                    candidate = self._screen(P, i0, i1, ncent) & chunk
            a, b, c = np.nonzero(candidate)
            a = a + i0
            # windows centered on no-data voxels have nothing to vote on
            centred = ~np.isnan(P[a + half[0], b + half[1], c + half[2]])
            a, b, c = a[centred], b[centred], c[centred]
            ws = getattr(local, "ws", None)
            if ws is None:
                ws = local.ws = _workspace(nwin, m)
            found = []
            for q in range(0, a.size, nwin):
                aa, bb, cc = a[q : q + nwin], b[q : q + nwin], c[q : q + nwin]
                W = V[aa, bb, cc].reshape(-1, m)
                outside = np.isnan(W)
                if outside.any():
                    W[outside] = 0.0
                    fl = _grubbsBatch(W, outside, self.gSmall, self.gLarge, ws)
                else:
                    fl = _grubbsBatch(W, None, self.gSmall, self.gLarge, ws)
                r, k = np.nonzero(fl)
                found.append((aa[r] * st0 + bb[r] * st1 + cc[r]) + offsets[k])
            return np.concatenate(found) if found else np.empty(0, dtype=np.intp)

        def add(positions: np.ndarray) -> None:
            if positions.size:
                np.add.at(flatVotes, positions, 1)

        starts = range(0, ncent[0], rowStep)
        if self.jobs <= 1:
            for i0 in starts:
                add(work(i0))
        else:
            with ThreadPoolExecutor(self.jobs) as executor:
                pending: deque = deque()
                for i0 in starts:
                    pending.append(executor.submit(work, i0))
                    if len(pending) >= 2 * self.jobs:
                        add(pending.popleft().result())
                while pending:
                    add(pending.popleft().result())

        return votes[
            half[0] : half[0] + shape[0],
            half[1] : half[1] + shape[1],
            half[2] : half[2] + shape[2],
        ].copy()


# --- replacement -----------------------------------------------------------------


def _kernelTables(window: tuple[int, ...]) -> list[np.ndarray]:
    """Per axis, normalized 1-D Gaussian weights for every truncation (lo
    members cut at the start, hi at the end): K[d][lo, hi] has length
    window[d], zero at truncated positions. exp(-(x²+y²+z²)/2) is separable,
    so the product of the three equals the normalized 3-D kernel."""
    tables = []
    for w in window:
        K = np.zeros((w, w, w))
        for lo in range(w):
            for hi in range(w - lo):
                x = np.linspace(-1, 1, w - lo - hi)
                g = np.exp(-(x**2) / 2.0)
                K[lo, hi, lo : w - hi] = g / g.sum()
        tables.append(K)
    return tables


def _replace(
    noise: np.ndarray,
    P: np.ndarray,
    F: np.ndarray,
    window: tuple[int, ...],
    half: tuple[int, ...],
    kernels: list[np.ndarray],
    batchMb: float,
) -> None:
    """Every flagged voxel gets the weighted average of its unflagged
    neighbors, using the values from before this round (order-independent)."""
    shape = noise.shape
    V = sliding_window_view(P, window)
    FP = np.zeros(P.shape, dtype=bool)
    FP[F[:, 0] + half[0], F[:, 1] + half[1], F[:, 2] + half[2]] = True
    VF = sliding_window_view(FP, window)
    nwin = _batchRows(int(np.prod(window)), batchMb)
    new = np.empty(F.shape[0])
    for q in range(0, F.shape[0], nwin):
        f = F[q : q + nwin]
        W = np.nan_to_num(V[f[:, 0], f[:, 1], f[:, 2]], nan=0.0)
        W[:, half[0], half[1], half[2]] = 0.0
        W[VF[f[:, 0], f[:, 1], f[:, 2]]] = 0.0
        lo = [np.maximum(0, half[d] - f[:, d]) for d in range(3)]
        hi = [np.maximum(0, f[:, d] + window[d] - half[d] - shape[d]) for d in range(3)]
        t = np.einsum("nabc,nc->nab", W, kernels[2][lo[2], hi[2]])
        t = np.einsum("nab,nb->na", t, kernels[1][lo[1], hi[1]])
        new[q : q + nwin] = np.einsum("na,na->n", t, kernels[0][lo[0], hi[0]])
    original = noise[F[:, 0], F[:, 1], F[:, 2]]
    new[new == original] = 0.0  # kept from the original implementation
    noise[F[:, 0], F[:, 1], F[:, 2]] = new
