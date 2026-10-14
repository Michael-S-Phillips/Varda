"""Checking a plugin before anyone enables it. The plugin runs in a separate
process with a timeout (``check_worker``), so code that crashes or hangs
can't take Varda down: it's imported, registered, and each analysis runs on
a synthetic cube and on a small crop of the user's image. A static scan adds
advisory warnings (network, subprocesses, eval, file writes).

No Qt: the agent's run_checks tool and the review dialog both use this."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from collections.abc import Sequence

import attrs
import numpy as np
from attrs import frozen

from varda.common.entities import VardaRaster
from varda.kindling.categories import duplicateOf

CHECK_FLAG = "--check-plugin"
TIMEOUT_SECONDS = 180
CROP_SIZE = 48  # pixels on a side, from the middle of the user's image
SYNTHETIC_SHAPE = (12, 12)
DEFAULT_WAVELENGTHS = np.linspace(400.0, 2500.0, 60)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console flash on Windows


@frozen
class RunResult:
    image: str  # "synthetic" or "your image"
    ok: bool
    seconds: float = 0.0
    shape: tuple[int, ...] = ()
    bandNames: tuple[str, ...] = ()
    nanFraction: float = 0.0
    error: str = ""
    unavailable: str = ""  # the analysis's own reason it can't run on this image


@frozen
class AnalysisResult:
    name: str
    analysisId: str
    category: str
    runs: tuple[RunResult, ...]

    @property
    def location(self) -> str:
        return f"Processing → {self.category} → {self.name}"


@frozen
class CheckReport:
    error: str = ""  # the plugin couldn't be loaded or checked at all
    analyses: tuple[AnalysisResult, ...] = ()
    dataSources: tuple[str, ...] = ()
    testsRan: bool = False
    testsOk: bool = False
    testsOutput: str = ""
    categoryProblems: tuple[str, ...] = ()  # menus that duplicate an existing one

    @property
    def passed(self) -> bool:
        runsOk = all(run.ok for a in self.analyses for run in a.runs)
        added = bool(self.analyses or self.dataSources)
        testsOk = self.testsOk or not self.testsRan
        return (
            not self.error
            and added
            and runsOk
            and testsOk
            and not self.categoryProblems
        )

    def withCategoriesChecked(self, categories: Sequence[str]) -> CheckReport:
        """Reject an analysis category that duplicates an existing Processing
        submenu ("Filters" beside "Filtering")."""
        problems = []
        for analysis in self.analyses:
            duplicate = duplicateOf(analysis.category, categories)
            if duplicate:
                problems.append(
                    f"{analysis.name}'s category {analysis.category!r} duplicates "
                    f"the existing {duplicate!r} menu: set category = {duplicate!r}."
                )
        return attrs.evolve(self, categoryProblems=tuple(dict.fromkeys(problems)))

    @classmethod
    def fromJson(cls, data: dict) -> CheckReport:
        analyses = tuple(
            AnalysisResult(
                a["name"],
                a["analysisId"],
                a["category"],
                tuple(_runResult(r) for r in a["runs"]),
            )
            for a in data.get("analyses", [])
        )
        return cls(
            error=data.get("error", ""),
            analyses=analyses,
            dataSources=tuple(data.get("dataSources", [])),
            testsRan=data.get("testsRan", False),
            testsOk=data.get("testsOk", False),
            testsOutput=data.get("testsOutput", ""),
        )

    def describe(self) -> str:
        """The report as text, for the model and for the review dialog."""
        if self.error:
            return f"FAILED before any analysis ran:\n{self.error}"
        lines = ["PASSED" if self.passed else "FAILED"]
        if not (self.analyses or self.dataSources):
            lines.append(
                "The plugin registered nothing (registerAnalyses returned no analyses)."
            )
        for analysis in self.analyses:
            lines.append(f"{analysis.name} ({analysis.location}):")
            for run in analysis.runs:
                if run.unavailable:
                    lines.append(f"  {run.image}: unavailable: {run.unavailable}")
                elif run.ok:
                    lines.append(
                        f"  {run.image}: ok in {run.seconds:.2f} s, shape {run.shape}, "
                        f"bands {list(run.bandNames)}, {run.nanFraction:.0%} NaN"
                    )
                else:
                    lines.append(f"  {run.image}: FAILED\n{_indent(run.error)}")
        lines += [f"Menu: {problem}" for problem in self.categoryProblems]
        for name in self.dataSources:
            lines.append(f"File format: {name} (registered; not run)")
        if self.testsRan:
            lines.append(
                f"Plugin tests: {'passed' if self.testsOk else 'FAILED'}\n{_indent(self.testsOutput)}"
            )
        else:
            lines.append(f"Plugin tests: not run. {self.testsOutput}".rstrip())
        return "\n".join(lines)


def _runResult(data: dict) -> RunResult:
    return RunResult(
        image=data["image"],
        ok=data["ok"],
        seconds=data.get("seconds", 0.0),
        shape=tuple(data.get("shape", ())),
        bandNames=tuple(data.get("bandNames", ())),
        nanFraction=data.get("nanFraction", 0.0),
        error=data.get("error", ""),
        unavailable=data.get("unavailable", ""),
    )


def _indent(text: str) -> str:
    return "\n".join("    " + line for line in text.strip().splitlines()[-40:])


# --- sample data -------------------------------------------------------------


def syntheticCube(wavelengths: np.ndarray) -> np.ndarray:
    """Smooth, plausible reflectance spectra with a few absorptions, on the
    user's wavelengths, so analyses that look for features find some."""
    rng = np.random.default_rng(0)
    span = float(np.ptp(wavelengths)) or 1.0
    tilt = 1 + 0.2 * (wavelengths - wavelengths.mean()) / span
    cube = rng.uniform(0.15, 0.5, SYNTHETIC_SHAPE)[..., None] * tilt
    for center in rng.uniform(wavelengths.min(), wavelengths.max(), 4):
        depth = rng.uniform(0.0, 0.2, SYNTHETIC_SHAPE)[..., None]
        cube = cube * (
            1 - depth * np.exp(-(((wavelengths - center) / (0.03 * span)) ** 2))
        )
    return cube.astype(np.float32)


def writeSample(image: VardaRaster | None, path: Path) -> None:
    """The images the checks run on: a synthetic cube on the image's
    wavelengths and a crop from the middle of the image (both stay on this
    computer). Without an image, only the synthetic cube, on 400-2500 nm."""
    centers = image.bandModel.centers if image is not None else None
    wavelengths = (
        np.asarray(centers, float) if centers is not None else DEFAULT_WAVELENGTHS
    )
    arrays: dict[str, np.ndarray] = {
        "synthetic": syntheticCube(wavelengths),
        "synthetic_wavelengths": wavelengths,
    }
    if image is not None:
        rows, cols = min(CROP_SIZE, image.height), min(CROP_SIZE, image.width)
        top, left = (image.height - rows) // 2, (image.width - cols) // 2
        crop = np.ma.filled(
            np.ma.asarray(
                image.getData(window=(top, left, rows, cols)), dtype=np.float32
            ),
            np.nan,
        )
        arrays["crop"] = crop
        if centers is not None:
            arrays["crop_wavelengths"] = np.asarray(centers, float)
        if image.nodata is not None:
            arrays["crop_nodata"] = np.asarray(image.nodata, float)
    np.savez(path, **arrays)  # ty: ignore[invalid-argument-type] (stub: a key could be allow_pickle)


# --- running the checks --------------------------------------------------------


def checkCommand(folder: Path, sample: Path, report: Path) -> list[str]:
    """Varda itself, in check mode: the packaged app's executable, or this
    Python running varda.main when Varda runs from source."""
    varda = (
        [sys.executable]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "varda.main"]
    )
    return [*varda, CHECK_FLAG, str(folder), str(sample), str(report)]


def runChecks(
    folder: Path,
    image: VardaRaster | None,
    categories: Sequence[str] = (),
    timeout: float = TIMEOUT_SECONDS,
) -> CheckReport:
    """Check the plugin in ``folder`` in a separate process; ``categories``
    are the Processing menu's existing submenus."""
    with tempfile.TemporaryDirectory(prefix="varda-check-") as scratch:
        sample, report = Path(scratch) / "sample.npz", Path(scratch) / "report.json"
        writeSample(image, sample)
        try:
            completed = subprocess.run(
                checkCommand(folder, sample, report),
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            return CheckReport(
                error=f"The checks took longer than {timeout:.0f} s and were stopped (an endless loop, or far too slow)."
            )
        if not report.is_file():
            output = (completed.stderr or completed.stdout or "").strip()
            return CheckReport(
                error=f"The check process exited with code {completed.returncode}:\n{output[-3000:]}"
            )
        result = CheckReport.fromJson(json.loads(report.read_text(encoding="utf-8")))
        return result.withCategoriesChecked(categories)


# --- static scan ----------------------------------------------------------------

RISKY_MODULES = {
    "socket": "uses the network (socket)",
    "urllib": "uses the network (urllib)",
    "http": "uses the network (http)",
    "requests": "uses the network (requests)",
    "httpx": "uses the network (httpx)",
    "subprocess": "starts other programs (subprocess)",
    "shutil": "can copy, move or delete files (shutil)",
    "ctypes": "calls native code (ctypes)",
    "pickle": "loads pickled data (pickle can run code)",
}
RISKY_CALLS = {
    "eval": "evaluates text as code (eval)",
    "exec": "runs text as code (exec)",
    "__import__": "imports modules by name (__import__)",
    "system": "runs a shell command (os.system)",
    "popen": "runs a shell command (os.popen)",
    "remove": "deletes files (os.remove)",
    "unlink": "deletes files (unlink)",
    "rmtree": "deletes folders (rmtree)",
}


def scanForWarnings(folder: Path) -> list[str]:
    """Advisory: things in the plugin's code a user should know about before
    enabling it. Not a security boundary."""
    warnings: list[str] = []
    for path in sorted(folder.rglob("*.py")):
        relative = path.relative_to(folder)
        if relative.parts[0] == "tests":
            continue  # tests run only in the check process
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            warnings.append(
                f"{relative}: doesn't parse ({error.msg}, line {error.lineno})"
            )
            continue
        for node in ast.walk(tree):
            line = f"{relative}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    top = name.split(".")[0]
                    if top in RISKY_MODULES:
                        warnings.append(f"{line}: {RISKY_MODULES[top]}")
                    elif top == "varda" and name != "varda.api":
                        warnings.append(
                            f"{line}: imports {name}, which isn't the plugin API and may change"
                        )
            elif isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", "")
                )
                if name in RISKY_CALLS:
                    warnings.append(f"{line}: {RISKY_CALLS[name]}")
                elif name == "open" and _writes(node):
                    warnings.append(f"{line}: writes a file (open for writing)")
    return list(dict.fromkeys(warnings))


def _writes(call: ast.Call) -> bool:
    modes = [a for a in call.args[1:2]] + [
        k.value for k in call.keywords if k.arg == "mode"
    ]
    return any(
        isinstance(m, ast.Constant)
        and isinstance(m.value, str)
        and set(m.value) & set("wax+")
        for m in modes
    )
