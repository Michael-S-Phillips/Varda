"""Balancing the inputs' brightness, per band, from where they overlap.

Statistics come from co-located pixels on a subsample of each overlap (as
ISIS ``equalizer``'s PERCENT parameter does), read with nearest-neighbor
resampling. Held images keep their values; the others are corrected:

- **Linear, to the held images:** each image overlapping a held one gets a
  robust regression of the held values on its own, per band.
- **Linear, global least squares** (as ISIS ``equalizer``): every overlap at
  once. Gains make the overlaps' standard deviations agree, then offsets
  make their means agree; each connected group of images needs a held one.
- **Histogram matching:** from the held images outward, each image's overlap
  histogram is mapped onto its already balanced neighbor's. Non-linear, so
  visual only.
"""

from __future__ import annotations

import math
import warnings
from collections import deque
from collections.abc import Callable, Iterable

import numpy as np
from affine import Affine
from attrs import frozen

from varda.mosaicking.recipe import Correction, LinearMode, RadiometryMethod
from varda.mosaicking.grid import TargetGrid, overlapGrid
from varda.mosaicking.model import MosaicError, MosaicProject
from varda.mosaicking.render import Resampling, readCube, sampleOnGrid

__all__ = [
    "Correction",
    "LinearMode",
    "RadiometryMethod",
    "RadiometryResult",
    "balance",
]

MAX_SAMPLES = 100_000  # co-located pixels per overlap, at most
MIN_SAMPLES = 50  # fewer and an overlap doesn't count
QUANTILES = 257  # histogram matching's lookup points
TRIM = 3.0  # robust regression: residuals beyond this many sigmas are dropped


@frozen
class RadiometryResult:
    method: RadiometryMethod
    mode: LinearMode
    held: frozenset[int]
    corrections: dict[int, Correction]  # by input key; held images get identity
    message: str = ""

    @property
    def visual(self) -> bool:
        return self.method is RadiometryMethod.HISTOGRAM


Pair = tuple[np.ndarray, np.ndarray]  # co-located samples (n, bands) of two inputs


def balance(
    project: MosaicProject,
    method: RadiometryMethod,
    mode: LinearMode = LinearMode.BOTH,
    held: Iterable[int] = (),
    progress: Callable[[float, str], None] = lambda fraction, message: None,
) -> RadiometryResult:
    """Fit the corrections (reads the project without changing it; apply the
    result with ``MosaicProject.applyRadiometry``)."""
    held = frozenset(held) or frozenset({project.inputs[0].key})
    bands = project.inputs[0].image.bandCount
    if method is RadiometryMethod.NONE:
        return RadiometryResult(method, mode, held, {})
    pairs = _overlapSamples(project, progress)
    neighbors: dict[int, set[int]] = {i.key: set() for i in project.inputs}
    for i, j in pairs:
        neighbors[i].add(j)
        neighbors[j].add(i)
    names = {i.key: i.image.name for i in project.inputs}
    identity = {k: Correction.identity(bands) for k in held}
    if method is RadiometryMethod.REFERENCE:
        corrections, unreached = _toHeld(pairs, neighbors, held, mode, bands)
    elif method is RadiometryMethod.GLOBAL:
        unreachable = set(neighbors) - _reachable(neighbors, held)
        if unreachable:
            raise MosaicError(
                f"{_list(names[k] for k in sorted(unreachable))} "
                f"{'doesn' if len(unreachable) == 1 else 'don'}'t overlap, directly "
                "or through other images, any held image. Hold one of "
                f"{'it' if len(unreachable) == 1 else 'them'} too, or hide "
                f"{'it' if len(unreachable) == 1 else 'them'}."
            )
        corrections, unreached = (
            _global(pairs, list(neighbors), held, mode, bands),
            set(),
        )
    else:
        corrections, unreached = _histograms(pairs, neighbors, held, bands)
    message = (
        f"{_list(names[k] for k in sorted(unreached))} "
        f"{'was' if len(unreached) == 1 else 'were'} left as they are: "
        + (
            "they don't overlap a held image."
            if method is RadiometryMethod.REFERENCE
            else "they don't overlap the balanced images."
        )
        if unreached
        else ""
    )
    return RadiometryResult(method, mode, held, identity | corrections, message)


def _list(names: Iterable[str]) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _overlapSamples(
    project: MosaicProject, progress: Callable[[float, str], None]
) -> dict[tuple[int, int], Pair]:
    """Co-located samples for every pair of overlapping inputs."""
    cubes = {}
    keys = [i.key for i in project.inputs]
    candidates = [(a, b) for n, a in enumerate(keys) for b in keys[n + 1 :]]
    pairs = {}
    for done, (a, b) in enumerate(candidates):
        progress(done / max(len(candidates), 1), "reading the overlaps")
        grid = overlapGrid(project, a, b)
        if grid is None:
            continue
        step = max(1, math.ceil(math.sqrt(grid.width * grid.height / MAX_SAMPLES)))
        coarse = TargetGrid(
            grid.transform * Affine.scale(step),
            max(grid.width // step, 1),
            max(grid.height // step, 1),
            grid.crs,
        )
        samples = []
        for key in (a, b):
            item = project.input(key)
            if key not in cubes:
                cubes[key] = readCube(item)
            values = sampleOnGrid(item, cubes[key], coarse, Resampling.NEAREST)
            samples.append(values.reshape(-1, values.shape[2]))
        # Pixels both images have data in (a band either is missing stays NaN
        # and is left out of that band's statistics)
        valid = np.isfinite(samples[0]).any(axis=1) & np.isfinite(samples[1]).any(
            axis=1
        )
        if valid.sum() >= MIN_SAMPLES:
            pairs[(a, b)] = (
                samples[0][valid].astype(float),
                samples[1][valid].astype(float),
            )
    return pairs


def _reachable(neighbors: dict[int, set[int]], held: frozenset[int]) -> set[int]:
    seen, queue = set(held), deque(held)
    while queue:
        for other in neighbors.get(queue.popleft(), ()):
            if other not in seen:
                seen.add(other)
                queue.append(other)
    return seen


def _samplesOf(pairs: dict[tuple[int, int], Pair], key: int, other: int) -> Pair:
    """(key's values, other's values) where they overlap."""
    if (key, other) in pairs:
        return pairs[(key, other)]
    b, a = pairs[(other, key)]
    return a, b


def _robustLine(x: np.ndarray, y: np.ndarray, mode: LinearMode) -> tuple[float, float]:
    """y ≈ gain·x + offset, refitted without residuals beyond TRIM sigmas;
    pairs missing either value are left out (gain 1, offset 0 if too few)."""
    finite = np.isfinite(x) & np.isfinite(y)
    if finite.sum() < MIN_SAMPLES:
        return 1.0, 0.0
    x, y = x[finite], y[finite]
    keep = np.ones(len(x), bool)
    gain, offset = 1.0, 0.0
    for _ in range(3):
        xs, ys = x[keep], y[keep]
        if mode is LinearMode.OFFSET:
            gain, offset = 1.0, float(np.median(ys - xs))
        elif mode is LinearMode.GAIN:
            gain, offset = float(xs @ ys / (xs @ xs)) if xs @ xs else 1.0, 0.0
        else:
            gain, offset = (
                np.polyfit(xs, ys, 1)
                if np.ptp(xs) > 0
                else (1.0, float(np.mean(ys - xs)))
            )
        residual = y - (gain * x + offset)
        spread = 1.4826 * np.median(np.abs(residual - np.median(residual)))
        if spread == 0:
            break
        keep = np.abs(residual) <= TRIM * spread
    return float(gain), float(offset)


def _toHeld(
    pairs: dict[tuple[int, int], Pair],
    neighbors: dict[int, set[int]],
    held: frozenset[int],
    mode: LinearMode,
    bands: int,
) -> tuple[dict[int, Correction], set[int]]:
    corrections, unreached = {}, set()
    for key, near in neighbors.items():
        if key in held:
            continue
        references = sorted(near & held)
        if not references:
            unreached.add(key)
            continue
        samples = [_samplesOf(pairs, key, other) for other in references]
        x = np.concatenate([s[0] for s in samples])
        y = np.concatenate([s[1] for s in samples])
        fits = [_robustLine(x[:, b], y[:, b], mode) for b in range(bands)]
        corrections[key] = Correction(
            np.array([g for g, _ in fits]), np.array([o for _, o in fits])
        )
    return corrections, unreached


def _global(
    pairs: dict[tuple[int, int], Pair],
    keys: list[int],
    held: frozenset[int],
    mode: LinearMode,
    bands: int,
) -> dict[int, Correction]:
    """ISIS equalizer's solution: gains so each overlap's standard deviations
    agree, then offsets so its means agree, by least squares over all
    overlaps (weighted by their size), held images fixed."""
    free = [k for k in keys if k not in held]
    column = {k: n for n, k in enumerate(free)}
    gains = np.ones((len(keys), bands))
    offsets = np.zeros((len(keys), bands))
    position = {k: n for n, k in enumerate(keys)}
    stats = {pair: _pairStats(a, b) for pair, (a, b) in pairs.items()}
    if free and mode is not LinearMode.OFFSET:
        for band in range(bands):
            rows, rhs = [], []
            for (i, j), (si, sj, _, _, n) in stats.items():
                if not (np.isfinite(si[band]) and np.isfinite(sj[band])):
                    continue  # too few pixels share this band
                row, value, weight = np.zeros(len(free)), 0.0, math.sqrt(n[band])
                for key, coefficient in ((i, si[band]), (j, -sj[band])):
                    if key in column:
                        row[column[key]] += coefficient * weight
                    else:
                        value -= coefficient * weight  # a held gain is 1
                rows.append(row)
                rhs.append(value)
            for key, solved in _solve(rows, rhs, column).items():
                gains[position[key], band] = solved
    if free and mode is not LinearMode.GAIN:
        for band in range(bands):
            rows, rhs = [], []
            for (i, j), (_, _, mi, mj, n) in stats.items():
                if not (np.isfinite(mi[band]) and np.isfinite(mj[band])):
                    continue
                row, weight = np.zeros(len(free)), math.sqrt(n[band])
                # (g_i·m_i + o_i) - (g_j·m_j + o_j) = 0
                value = (
                    gains[position[j], band] * mj[band]
                    - gains[position[i], band] * mi[band]
                ) * weight
                for key, sign in ((i, 1.0), (j, -1.0)):
                    if key in column:
                        row[column[key]] += sign * weight
                rows.append(row)
                rhs.append(value)
            for key, solved in _solve(rows, rhs, column).items():
                offsets[position[key], band] = solved
    return {k: Correction(gains[position[k]], offsets[position[k]]) for k in free}


def _solve(
    rows: list[np.ndarray], rhs: list[float], column: dict[int, int]
) -> dict[int, float]:
    """The least-squares values of the images the equations constrain (an
    image with no usable overlap in a band keeps its default)."""
    if not rows:
        return {}
    matrix = np.array(rows)
    solution = np.linalg.lstsq(matrix, np.array(rhs), rcond=None)[0]
    return {
        key: float(solution[n]) for key, n in column.items() if np.any(matrix[:, n])
    }


def _pairStats(
    a: np.ndarray, b: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per band: each image's standard deviation and mean over the pixels
    both have that band in, and how many there are (NaN statistics where
    too few)."""
    both = np.isfinite(a) & np.isfinite(b)
    counts = both.sum(axis=0)
    a, b = np.where(both, a, np.nan), np.where(both, b, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # empty bands stay NaN
        stats = [
            np.nanstd(a, axis=0),
            np.nanstd(b, axis=0),
            np.nanmean(a, axis=0),
            np.nanmean(b, axis=0),
        ]
    few = counts < MIN_SAMPLES
    for value in stats:
        value[few] = np.nan
    return stats[0], stats[1], stats[2], stats[3], counts


def _histograms(
    pairs: dict[tuple[int, int], Pair],
    neighbors: dict[int, set[int]],
    held: frozenset[int],
    bands: int,
) -> tuple[dict[int, Correction], set[int]]:
    """Breadth first from the held images: each image's overlap values are
    matched, quantile by quantile, to its balanced neighbor's (corrected)."""
    corrections: dict[int, Correction] = {k: Correction.identity(bands) for k in held}
    queue = deque(sorted(held))
    levels = np.linspace(0, 100, QUANTILES)
    while queue:
        done = queue.popleft()
        for key in sorted(neighbors[done] - set(corrections)):
            mine, theirs = _samplesOf(pairs, key, done)
            theirs = corrections[done].apply(theirs)
            ins, outs = [], []
            for b in range(bands):
                both = np.isfinite(mine[:, b]) & np.isfinite(theirs[:, b])
                if both.sum() < MIN_SAMPLES:  # nothing to match: leave the band
                    ins.append(levels.copy())
                    outs.append(levels.copy())
                    continue
                lutIn = np.percentile(mine[both, b], levels)
                lutOut = np.percentile(theirs[both, b], levels)
                x, first = np.unique(lutIn, return_index=True)  # increasing
                ins.append(np.interp(levels, np.linspace(0, 100, len(x)), x))
                outs.append(
                    np.interp(levels, np.linspace(0, 100, len(x)), lutOut[first])
                )
            corrections[key] = Correction(
                np.ones(bands), np.zeros(bands), np.array(ins), np.array(outs)
            )
            queue.append(key)
    unreached = set(neighbors) - set(corrections)
    return {k: v for k, v in corrections.items() if k not in held}, unreached
