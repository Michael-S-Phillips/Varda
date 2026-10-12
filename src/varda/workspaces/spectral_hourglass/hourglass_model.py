"""State of a spectral hourglass run: prepare → MNF → PPI → endmembers →
identify → map.

Qt-free. Long computations are split in two so signals never fire from a
worker thread: ``xxxTask(...)`` returns a callable that computes from a
snapshot of the current state and returns a result object (run it in the
background), and ``applyXxx(result)`` stores it (call it on the GUI thread).

Every step's result is kept; re-running a step marks the steps that depend
on it STALE rather than discarding them, so the user can go back, change one
choice and see what else needs redoing. Endmember pixels are flat image
indices (row * width + col), so classes survive re-runs of earlier steps.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from enum import Enum

import attrs
import numpy as np
from psygnal import Signal

from varda.analysis.endmembers import pixelPurityIndex, suggestGroups
from varda.analysis.iovf import iovfFilter
from varda.analysis.linear_algebra import (
    TransformResult,
    flattenValid,
    mnf,
    noiseCovariance,
    suggestedComponents,
)
from varda.analysis.rasters import readCube
from varda.analysis.unmixing import (
    Constraint,
    linearUnmix,
    mixtureTunedMatchedFilter,
    spectralAngles,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

ProgressCallback = Callable[[int, str], None]

# Distinct, colour-blind-friendly-ish class colours (Kelly / Tol mixes)
PALETTE = [
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#42d4f4",
    "#f032e6",
    "#bfef45",
    "#fabed4",
    "#469990",
    "#dcbeff",
    "#9a6324",
    "#fffac8",
    "#800000",
    "#aaffc3",
    "#808000",
    "#ffd8b1",
    "#000075",
]

DEFAULT_PPI_ITERATIONS = 10_000
DEFAULT_PPI_THRESHOLD = 2.5  # MNF units = noise sigmas
DEFAULT_MAX_CANDIDATES = 2_000
DEFAULT_SAM_MAX_ANGLE = 0.10  # radians, ENVI's default


class Step(Enum):
    PREPARE = "Prepare"
    REDUCE = "Reduce (MNF)"
    PURITY = "Pixel Purity"
    ENDMEMBERS = "Endmembers"
    IDENTIFY = "Identify"
    MAP = "Map"


class StepState(Enum):
    NOT_RUN = "not run"
    DONE = "done"
    STALE = "needs re-running"


class MapMethod(Enum):
    SAM = "Spectral Angle Mapper (SAM)"
    UNMIX = "Linear Spectral Unmixing"
    MTMF = "Mixture Tuned Matched Filtering (MTMF)"


# Which computed steps each step's result depends on
_DEPENDS_ON: dict[Step, tuple[Step, ...]] = {
    Step.REDUCE: (Step.PREPARE,),
    Step.PURITY: (Step.REDUCE,),
}


@attrs.define
class HourglassSettings:
    wavelengthRange: tuple[float, float] | None = None  # keep bands inside (inclusive)
    useIovf: bool = False


@attrs.define(eq=False)
class Endmember:
    id: int
    name: str
    color: str  # "#rrggbb"
    pixels: np.ndarray = attrs.field(factory=lambda: np.empty(0, dtype=np.int64))
    identification: str = ""  # best library match, e.g. "Kaolinite (0.91)"


@attrs.frozen
class PreparedData:
    cube: np.ndarray  # float64 (rows, cols, bands), unusable pixels NaN
    valid: np.ndarray  # bool (rows, cols)
    wavelengths: np.ndarray | None  # numeric band centres, or None
    bandIndices: np.ndarray  # indices of the kept bands in the source image


@attrs.frozen
class PpiResult:
    counts: np.ndarray  # int64, one per valid pixel (flattenValid order)
    iterations: int
    threshold: float


class HourglassModel:
    sigStepChanged = Signal(object)  # Step
    sigEndmembersChanged = Signal()
    sigCandidatesChanged = Signal()

    def __init__(self, image: VardaRaster) -> None:
        self.image = image
        self.settings = HourglassSettings()
        self._states = {step: StepState.NOT_RUN for step in Step}
        self.prepared: PreparedData | None = None
        self.mnf: TransformResult | None = None
        self.components = 0
        self.ppi: PpiResult | None = None
        self.minCount = 1
        self.maxCandidates = DEFAULT_MAX_CANDIDATES
        self.endmembers: list[Endmember] = []
        self._nextId = 1
        self._validFlat: np.ndarray | None = None  # flat indices of valid pixels

    # --- state ---------------------------------------------------------------

    def state(self, step: Step) -> StepState:
        return self._states[step]

    def _setState(self, step: Step, state: StepState) -> None:
        if self._states[step] is not state:
            self._states[step] = state
            self.sigStepChanged.emit(step)

    def _markDone(self, step: Step) -> None:
        self._setState(step, StepState.DONE)
        for downstream, upstream in _DEPENDS_ON.items():
            if step in upstream and self._states[downstream] is StepState.DONE:
                self._markStale(downstream)

    def _markStale(self, step: Step) -> None:
        self._setState(step, StepState.STALE)
        for downstream, upstream in _DEPENDS_ON.items():
            if step in upstream and self._states[downstream] is StepState.DONE:
                self._markStale(downstream)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.image.height, self.image.width)

    # --- 1. prepare ------------------------------------------------------------

    @property
    def cube(self) -> np.ndarray:
        return self._require(self.prepared, Step.PREPARE).cube

    @property
    def valid(self) -> np.ndarray:
        return self._require(self.prepared, Step.PREPARE).valid

    @property
    def wavelengths(self) -> np.ndarray | None:
        return self._require(self.prepared, Step.PREPARE).wavelengths

    def prepareTask(self) -> Callable[[ProgressCallback], PreparedData]:
        image = self.image
        settings = attrs.evolve(self.settings)

        def task(progress: ProgressCallback) -> PreparedData:
            progress(0, "reading image")
            numeric = (
                None
                if image.wavelengthsType is str
                else np.asarray(image.wavelengths, float)
            )
            indices = np.arange(image.bandCount)
            if settings.wavelengthRange is not None and numeric is not None:
                lo, hi = settings.wavelengthRange
                indices = np.flatnonzero((numeric >= lo) & (numeric <= hi))
                if indices.size < 3:
                    raise ValueError(
                        "Fewer than three bands fall inside the wavelength range."
                    )
            cube, valid = readCube(image)
            cube = np.ascontiguousarray(cube[:, :, indices])
            if settings.useIovf:
                result = iovfFilter(
                    cube,
                    progress=lambda p, m: progress(10 + int(0.85 * p), f"IOVF {m}"),
                )
                cube = result.filtered
                cube[~valid] = np.nan
            progress(100, "done")
            return PreparedData(
                cube=cube,
                valid=valid,
                wavelengths=None if numeric is None else numeric[indices],
                bandIndices=indices,
            )

        return task

    def applyPrepared(self, prepared: PreparedData) -> None:
        self.prepared = prepared
        self._validFlat = np.flatnonzero(prepared.valid.ravel())
        self._markDone(Step.PREPARE)

    # --- 2. reduce (MNF) ---------------------------------------------------------

    def mnfTask(self) -> Callable[[ProgressCallback], TransformResult]:
        prepared = self._require(self.prepared, Step.PREPARE)

        def task(progress: ProgressCallback) -> TransformResult:
            progress(0, "estimating noise")
            X, valid = flattenValid(prepared.cube, None)
            noise = noiseCovariance(prepared.cube, valid)
            progress(30, "computing components")
            result = mnf(X, noise, X.shape[1])
            progress(100, "done")
            return result

        return task

    def applyMnf(self, result: TransformResult) -> None:
        self.mnf = result
        self.components = suggestedComponents(result.eigenvalues, "MNF")
        self._markDone(Step.REDUCE)

    def setComponents(self, count: int) -> None:
        result = self._require(self.mnf, Step.REDUCE)
        count = int(np.clip(count, 1, result.scores.shape[1]))
        if count != self.components:
            self.components = count
            if self._states[Step.PURITY] is StepState.DONE:
                self._markStale(Step.PURITY)
            self.sigStepChanged.emit(Step.REDUCE)

    def componentImage(self, index: int) -> np.ndarray:
        """(rows, cols) MNF component ``index`` (0-based), NaN where invalid."""
        result = self._require(self.mnf, Step.REDUCE)
        return self._toImage(result.scores[:, index])

    def _toImage(self, values: np.ndarray) -> np.ndarray:
        image = np.full(self.shape[0] * self.shape[1], np.nan)
        image[self._requireValidFlat()] = values
        return image.reshape(self.shape)

    def _requireValidFlat(self) -> np.ndarray:
        if self._validFlat is None:
            raise ValueError("Run Prepare first.")
        return self._validFlat

    # --- 3. pixel purity -----------------------------------------------------------

    @property
    def ppiIterations(self) -> int:
        return 0 if self.ppi is None else self.ppi.iterations

    def ppiTask(
        self,
        iterations: int = DEFAULT_PPI_ITERATIONS,
        threshold: float = DEFAULT_PPI_THRESHOLD,
        *,
        seed: int | None = None,
        resume: bool = False,
    ) -> Callable[[ProgressCallback], PpiResult]:
        result = self._require(self.mnf, Step.REDUCE)
        X = result.scores[:, : self.components]
        previous = self.ppi if resume and self.ppi is not None else None

        def task(progress: ProgressCallback) -> PpiResult:
            counts = pixelPurityIndex(
                X,
                iterations,
                threshold,
                seed=seed,
                start=None if previous is None else previous.counts,
                progress=progress,
            )
            done = iterations + (0 if previous is None else previous.iterations)
            return PpiResult(counts=counts, iterations=done, threshold=threshold)

        return task

    def applyPpi(self, result: PpiResult) -> None:
        self.ppi = result
        self._markDone(Step.PURITY)
        self.sigCandidatesChanged.emit()

    def ppiImage(self) -> np.ndarray:
        ppi = self._require(self.ppi, Step.PURITY)
        return self._toImage(ppi.counts.astype(np.float64))

    def setCandidateRule(self, minCount: int, maxCandidates: int) -> None:
        self.minCount = max(1, int(minCount))
        self.maxCandidates = max(1, int(maxCandidates))
        self.sigCandidatesChanged.emit()

    def _candidateRows(self) -> np.ndarray:
        """Rows of the valid-pixel matrix that are candidates, highest PPI first."""
        ppi = self._require(self.ppi, Step.PURITY)
        rows = np.flatnonzero(ppi.counts >= self.minCount)
        order = np.argsort(-ppi.counts[rows], kind="stable")
        return rows[order][: self.maxCandidates]

    def candidatePixels(self) -> np.ndarray:
        """Flat image indices of the candidate pure pixels, highest PPI first."""
        return self._requireValidFlat()[self._candidateRows()]

    def ndPoints(self) -> np.ndarray:
        """MNF coordinates (candidates, components) of the candidate pixels."""
        result = self._require(self.mnf, Step.REDUCE)
        return result.scores[self._candidateRows(), : self.components]

    def mnfCoordinates(self, pixels: Sequence[int] | np.ndarray) -> np.ndarray:
        """MNF coordinates (pixels, components) of flat image indices (NaN for
        invalid pixels)."""
        result = self._require(self.mnf, Step.REDUCE)
        rows = self._validRows(np.asarray(pixels, dtype=np.int64))
        out = np.full((rows.size, self.components), np.nan)
        ok = rows >= 0
        out[ok] = result.scores[rows[ok], : self.components]
        return out

    def _validRows(self, pixels: np.ndarray) -> np.ndarray:
        """Row in the valid-pixel matrix of each flat index (-1 if invalid)."""
        validFlat = self._requireValidFlat()
        pos = np.searchsorted(validFlat, pixels)
        pos = np.clip(pos, 0, max(validFlat.size - 1, 0))
        found = validFlat.size > 0
        return np.where(found & (validFlat[pos] == pixels), pos, -1)

    def backgroundSample(self, count: int = 5_000, seed: int = 0) -> np.ndarray:
        """MNF coordinates of a random sample of all valid pixels, for context
        behind the candidates in the n-D view."""
        result = self._require(self.mnf, Step.REDUCE)
        n = result.scores.shape[0]
        rows = np.random.default_rng(seed).choice(n, size=min(count, n), replace=False)
        return result.scores[np.sort(rows), : self.components]

    # --- 4. endmembers ---------------------------------------------------------------

    def endmember(self, endmemberId: int) -> Endmember:
        for endmember in self.endmembers:
            if endmember.id == endmemberId:
                return endmember
        raise KeyError(endmemberId)

    def addEndmember(
        self, name: str | None = None, color: str | None = None
    ) -> Endmember:
        used = {e.color for e in self.endmembers}
        if color is None:
            color = next(
                (c for c in PALETTE if c not in used), PALETTE[len(used) % len(PALETTE)]
            )
        endmember = Endmember(
            id=self._nextId, name=name or f"Endmember {self._nextId}", color=color
        )
        self._nextId += 1
        self.endmembers.append(endmember)
        self._endmembersChanged()
        return endmember

    def removeEndmember(self, endmemberId: int) -> None:
        self.endmembers = [e for e in self.endmembers if e.id != endmemberId]
        self._endmembersChanged()

    def renameEndmember(self, endmemberId: int, name: str) -> None:
        self.endmember(endmemberId).name = (
            name.strip() or self.endmember(endmemberId).name
        )
        self._endmembersChanged()

    def setIdentification(self, endmemberId: int, text: str) -> None:
        self.endmember(endmemberId).identification = text
        self._endmembersChanged()

    def recolorEndmember(self, endmemberId: int, color: str) -> None:
        self.endmember(endmemberId).color = color
        self._endmembersChanged()

    def assignPixels(
        self, endmemberId: int, pixels: Iterable[int], *, add: bool = True
    ) -> None:
        """Add ``pixels`` (flat indices) to an endmember, taking them from any
        other; or with ``add=False`` remove them from it."""
        chosen = np.unique(np.asarray(list(pixels), dtype=np.int64))
        target = self.endmember(endmemberId)
        if add:
            for other in self.endmembers:
                if other is not target:
                    other.pixels = np.setdiff1d(other.pixels, chosen)
            target.pixels = np.union1d(target.pixels, chosen)
        else:
            target.pixels = np.setdiff1d(target.pixels, chosen)
        self._endmembersChanged()

    def mergeEndmembers(self, endmemberIds: Sequence[int]) -> Endmember:
        """Merge into the first of ``endmemberIds`` (keeping its name and colour)."""
        keep = self.endmember(endmemberIds[0])
        for other in [self.endmember(i) for i in endmemberIds[1:]]:
            keep.pixels = np.union1d(keep.pixels, other.pixels)
            self.endmembers.remove(other)
        self._endmembersChanged()
        return keep

    def suggestEndmembers(self, count: int, seed: int = 0) -> list[Endmember]:
        """Group the candidate pixels into ``count`` new endmembers by k-means
        in MNF space (ENVI's auto-cluster)."""
        pixels = self.candidatePixels()
        labels = suggestGroups(self.ndPoints(), count, seed=seed)
        created = []
        with self.sigEndmembersChanged.blocked():
            for label in range(count):
                endmember = self.addEndmember()
                self.assignPixels(endmember.id, pixels[labels == label])
                created.append(endmember)
        self._endmembersChanged()
        return created

    def endmemberSpectrum(self, endmemberId: int) -> np.ndarray:
        """Mean prepared spectrum of an endmember's valid pixels (NaN if none)."""
        cube = self.cube
        pixels = self.endmember(endmemberId).pixels
        flat = cube.reshape(-1, cube.shape[2])[pixels]
        flat = flat[np.all(np.isfinite(flat), axis=1)]
        if flat.size == 0:
            return np.full(cube.shape[2], np.nan)
        return flat.mean(axis=0)

    def usableEndmembers(self) -> list[Endmember]:
        return [e for e in self.endmembers if e.pixels.size]

    def _endmembersChanged(self) -> None:
        state = StepState.DONE if self.usableEndmembers() else StepState.NOT_RUN
        self._setState(Step.ENDMEMBERS, state)
        self.sigEndmembersChanged.emit()

    def endmembersToJson(self) -> dict:
        return {
            "image": self.image.name,
            "shape": list(self.shape),
            "endmembers": [
                {
                    "name": e.name,
                    "color": e.color,
                    "identification": e.identification,
                    "pixels": e.pixels.tolist(),
                }
                for e in self.endmembers
            ],
        }

    def endmembersFromJson(self, data: dict) -> None:
        """Replace the endmembers with those saved by ``endmembersToJson``."""
        if list(data.get("shape", self.shape)) != list(self.shape):
            raise ValueError(
                "Those endmembers were picked on an image of a different size."
            )
        self.endmembers = []
        with self.sigEndmembersChanged.blocked():
            for entry in data["endmembers"]:
                endmember = self.addEndmember(entry["name"], entry["color"])
                endmember.pixels = np.asarray(entry["pixels"], dtype=np.int64)
                endmember.identification = entry.get("identification", "")
        self._endmembersChanged()

    # --- 5. identify -------------------------------------------------------------------

    def markIdentified(self) -> None:
        self._setState(Step.IDENTIFY, StepState.DONE)

    # --- 6. map ------------------------------------------------------------------------

    def mapTask(
        self,
        method: MapMethod,
        *,
        maxAngle: float = DEFAULT_SAM_MAX_ANGLE,
        constraint: Constraint = Constraint.FULLY_CONSTRAINED,
    ) -> Callable[[ProgressCallback], VardaRaster]:
        endmembers = self.usableEndmembers()
        if len(endmembers) < 2:
            raise ValueError("Mapping needs at least two endmembers with pixels.")
        prepared = self._require(self.prepared, Step.PREPARE)
        names = [e.name for e in endmembers]
        colors = [e.color for e in endmembers]
        spectra = np.stack([self.endmemberSpectrum(e.id) for e in endmembers])
        validFlat = self._requireValidFlat()
        if method is MapMethod.MTMF:
            mnfResult = self._require(self.mnf, Step.REDUCE)
            k = self.components
            mnfData = mnfResult.scores[:, :k]
            targets = np.stack(
                [np.nanmean(self.mnfCoordinates(e.pixels), axis=0) for e in endmembers]
            )
        image = self.image
        shape = self.shape

        def toImage(values: np.ndarray) -> np.ndarray:
            out = np.full(
                (shape[0] * shape[1], values.shape[1]), np.nan, dtype=np.float32
            )
            out[validFlat] = values
            return out.reshape(shape + (values.shape[1],))

        def task(progress: ProgressCallback) -> VardaRaster:
            progress(0, "mapping")
            X = prepared.cube.reshape(-1, prepared.cube.shape[2])[validFlat]
            if method is MapMethod.SAM:
                angles = spectralAngles(X, spectra)
                classes = np.argmin(np.nan_to_num(angles, nan=np.inf), axis=1).astype(
                    float
                )
                classes[np.nanmin(angles, axis=1) > maxAngle] = np.nan
                bands = np.column_stack([classes, angles])
                bandNames = ["Class", *[f"Angle({n})" for n in names]]
                suffix = "SAM"
                detail = f"max angle {maxAngle:g} rad"
            elif method is MapMethod.UNMIX:
                abundances, rmse = linearUnmix(X, spectra, constraint)
                bands = np.column_stack([abundances, rmse])
                bandNames = [*names, "RMS Error"]
                suffix = "unmixing"
                detail = constraint.value
            else:
                mf, infeasibility = mixtureTunedMatchedFilter(mnfData, targets)
                bands = np.column_stack([mf, infeasibility])
                bandNames = [
                    *[f"MF({n})" for n in names],
                    *[f"Infeasibility({n})" for n in names],
                ]
                suffix = "MTMF"
                detail = f"{k} MNF components"
            progress(90, "building image")
            source = ArrayDataSource(
                toImage(bands),
                wavelengths=np.array(bandNames),
                wavelengthUnits="endmembers",
                bandNames=bandNames,
                transform=image.transform,
                crs=image.crs,
                description=f"{method.value} of {image.name} ({detail})",
                extraMetadata={"classes": names, "classColors": colors},
            )
            progress(100, "done")
            return VardaRaster(source, name=f"{image.name} {suffix}")

        return task

    def applyMap(self, result: VardaRaster) -> VardaRaster:
        self._setState(Step.MAP, StepState.DONE)
        return result

    # --- helpers -------------------------------------------------------------------------

    @staticmethod
    def _require(value, step: Step):
        if value is None:
            raise ValueError(f"Run the {step.value} step first.")
        return value
