"""The app-managed PyTorch environment for the CNN and ViT classifiers.

PyTorch is too large to ship in every download, so on request Varda builds a
separate Python environment in its app-data folder with the bundled ``uv``:

1. ``uv venv`` with a uv-managed CPython 3.13 (the user's Pythons are ignored).
2. ``uv pip sync`` of a pinned, hashed lock for the platform and hardware,
   from ``resources/optional_features/torch``.
3. A probe that imports torch through the worker and records the result in
   ``manifest.json``, which marks the install complete.

Classifiers then run in that environment's interpreter with
``python -m varda_torch_worker``. Uninstalling deletes the one folder.
Regenerate the locks with ``scripts/compile_torch_locks.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QStandardPaths

from varda.utilities.resources import resource_path
from varda.version import vardaVersion
import varda_torch_worker
from varda_torch_worker import protocol

RUNTIME_LAYOUT = 1  # bump if the folder layout changes
PYTHON_VERSION = "3.13"
PYTHON_DOWNLOAD_MB = 17  # uv's managed CPython 3.13
LOW_SPACE_FACTOR = 5  # installed size is roughly 2-5x the download
MIN_CUDA13_DRIVER = 580  # NVIDIA driver major version for CUDA 13.0
MIN_CUDA13_CAPABILITY = 7.5  # Turing; CUDA 13 dropped Maxwell, Pascal and Volta
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console flash on Windows


@dataclass(frozen=True)
class Backend:
    key: str  # also the lock file's name
    label: str
    torchBackend: str | None  # uv --torch-backend; None for the PyPI build


BACKENDS = {
    b.key: b
    for b in (
        Backend("macos-arm64", "Apple silicon (Metal GPU)", None),
        Backend("windows-x64-cpu", "CPU only", "cpu"),
        Backend("windows-x64-cu130", "NVIDIA GPU (CUDA 13.0)", "cu130"),
        Backend("linux-x64-cpu", "CPU only", "cpu"),
        Backend("linux-x64-cu130", "NVIDIA GPU (CUDA 13.0)", "cu130"),
    )
}


def _platformPrefix(system: str, machine: str) -> str | None:
    machine = machine.lower()
    if system == "Darwin" and machine == "arm64":
        return "macos-arm64"
    if machine in {"x86_64", "amd64"}:
        return {"Windows": "windows-x64", "Linux": "linux-x64"}.get(system)
    return None


def platformBackends(
    system: str | None = None, machine: str | None = None
) -> list[Backend]:
    """The builds this computer can install, CPU first."""
    prefix = _platformPrefix(system or platform.system(), machine or platform.machine())
    if prefix is None:
        return []
    return [b for key, b in BACKENDS.items() if key.startswith(prefix)]


def _queryNvidiaSmi() -> str | None:
    """'driver, compute capability, name' of the first NVIDIA GPU, if any."""
    smi = shutil.which("nvidia-smi")
    if smi is None:
        return None
    try:
        completed = subprocess.run(
            [
                smi,
                "--query-gpu=driver_version,compute_cap,name",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = completed.stdout.strip().splitlines()
    return lines[0] if completed.returncode == 0 and lines else None


def detectBackend(
    system: str | None = None,
    machine: str | None = None,
    nvidiaSmi: Callable[[], str | None] = _queryNvidiaSmi,
) -> Backend | None:
    """The best build for this computer: Apple GPU on Apple silicon, CUDA 13
    when a recent enough NVIDIA GPU and driver are present, otherwise CPU."""
    choices = {b.torchBackend: b for b in platformBackends(system, machine)}
    if not choices:
        return None
    if None in choices:
        return choices[None]
    gpu = nvidiaSmi()
    if gpu and "cu130" in choices:
        try:
            driver, capability = (part.strip() for part in gpu.split(",")[:2])
            if (
                int(driver.split(".")[0]) >= MIN_CUDA13_DRIVER
                and float(capability) >= MIN_CUDA13_CAPABILITY
            ):
                return choices["cu130"]
        except ValueError:
            pass
    return choices["cpu"]


class InstallError(RuntimeError):
    pass


class InstallCancelled(InstallError):
    pass


class TorchRuntime:
    """One PyTorch environment under ``root``."""

    def __init__(self, root: Path, uv: list[str], workerDir: Path, lockDir: Path):
        self.root = Path(root)
        self.uv = uv
        self.workerDir = Path(workerDir)
        self.lockDir = Path(lockDir)
        self.envDir = self.root / "env"
        self.manifestPath = self.root / "manifest.json"

    # --- state ---------------------------------------------------------------

    def pythonPath(self) -> Path:
        if sys.platform == "win32":
            return self.envDir / "Scripts" / "python.exe"
        return self.envDir / "bin" / "python"

    def lockPath(self, backend: Backend) -> Path:
        return self.lockDir / f"{backend.key}.txt"

    def lockHash(self, backend: Backend) -> str:
        return hashlib.sha256(self.lockPath(backend).read_bytes()).hexdigest()

    def downloadMB(self, backend: Backend) -> float:
        """The install's download: the locked wheels (measured when the locks
        were compiled, in ``sizes.json``) plus the Python interpreter."""
        sizes = json.loads((self.lockDir / "sizes.json").read_text())
        return sizes[backend.key] / 1e6 + PYTHON_DOWNLOAD_MB

    def manifest(self) -> dict | None:
        try:
            return json.loads(self.manifestPath.read_text())
        except (OSError, ValueError):
            return None

    def isInstalled(self) -> bool:
        return self.manifest() is not None and self.pythonPath().exists()

    def installedBackend(self) -> Backend | None:
        manifest = self.manifest()
        return BACKENDS.get(manifest["backend"]) if manifest else None

    def updateAvailable(self) -> bool:
        """True when this Varda pins a different PyTorch than the installed one."""
        manifest, backend = self.manifest(), self.installedBackend()
        if manifest is None or backend is None:
            return False
        return (
            manifest.get("lockSha256") != self.lockHash(backend)
            or manifest.get("layout") != RUNTIME_LAYOUT
        )

    def writeManifest(self, backend: Backend, probe: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "layout": RUNTIME_LAYOUT,
            "backend": backend.key,
            "lockSha256": self.lockHash(backend),
            "torch": probe["torch"],
            "device": probe["device"],
            "vardaVersion": vardaVersion(),
            "installedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.manifestPath.write_text(json.dumps(manifest, indent=2))

    def uninstall(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def removeEnvironment(self) -> None:
        """Drop the environment and manifest but keep uv's download cache."""
        self.manifestPath.unlink(missing_ok=True)
        shutil.rmtree(self.envDir, ignore_errors=True)

    # --- commands ------------------------------------------------------------

    def installEnv(self) -> dict[str, str]:
        """uv's environment: everything inside ``root``, user config ignored."""
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("UV_")
            and k not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "CONDA_PREFIX"}
        }
        env.update(
            UV_CACHE_DIR=str(self.root / "cache"),
            UV_PYTHON_INSTALL_DIR=str(self.root / "python"),
            UV_NO_CONFIG="1",
            UV_NO_PROGRESS="1",
        )
        return env

    def installCommands(self, backend: Backend) -> list[list[str]]:
        venv = [
            *self.uv,
            "venv",
            str(self.envDir),
            "--python",
            PYTHON_VERSION,
            "--python-preference",
            "only-managed",
            "--no-project",
        ]
        sync = [
            *self.uv,
            "pip",
            "sync",
            str(self.lockPath(backend)),
            "--python",
            str(self.pythonPath()),
            "--require-hashes",
        ]
        if backend.torchBackend is not None:
            sync += ["--torch-backend", backend.torchBackend]
        return [venv, sync]

    def workerEnv(self) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
        }
        env.update(PYTHONPATH=str(self.workerDir), PYTHONNOUSERSITE="1")
        return env

    def probeCommand(self) -> list[str]:
        return [str(self.pythonPath()), "-m", "varda_torch_worker", "--probe"]

    # --- jobs ----------------------------------------------------------------

    def runJob(
        self,
        cube: np.ndarray,
        valid: np.ndarray,
        rows: np.ndarray,
        cols: np.ndarray,
        labels: np.ndarray,
        *,
        classes: int,
        spec: dict,
        progress: Callable[[float, str], None],
    ) -> tuple[np.ndarray, dict]:
        """Train and classify in the worker process; blocks until it is done."""
        with tempfile.TemporaryDirectory(prefix="varda-torch-") as jobDir:
            protocol.writeJob(
                Path(jobDir),
                cube,
                valid,
                rows,
                cols,
                labels,
                classes=classes,
                spec=spec,
            )
            errorLog = Path(jobDir) / "stderr.txt"
            error = None
            with errorLog.open("w") as stderr:
                process = subprocess.Popen(
                    [str(self.pythonPath()), "-m", "varda_torch_worker", jobDir],
                    stdout=subprocess.PIPE,
                    stderr=stderr,  # a file, so a chatty worker can't block
                    text=True,
                    env=self.workerEnv(),
                    creationflags=_NO_WINDOW,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue  # stray print from a library
                    if "progress" in message:
                        progress(message["progress"], message.get("message", ""))
                    elif "error" in message:
                        error = message["error"]
                returnCode = process.wait()
            if returnCode != 0:
                detail = error or errorLog.read_text().strip()[-2000:]
                raise RuntimeError(f"The PyTorch worker failed: {detail}")
            return protocol.readResult(Path(jobDir))


class Installer:
    """Runs the install steps, streaming their output; ``cancel`` from any thread."""

    def __init__(
        self,
        runtime: TorchRuntime,
        backend: Backend,
        onLog: Callable[[str], None],
        onStep: Callable[[str], None],
    ):
        self.runtime = runtime
        self.backend = backend
        self.onLog = onLog
        self.onStep = onStep
        self._process: subprocess.Popen | None = None
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def run(self) -> None:
        runtime = self.runtime
        venv, sync = runtime.installCommands(self.backend)
        env = runtime.installEnv()
        try:
            runtime.removeEnvironment()
            runtime.root.mkdir(parents=True, exist_ok=True)
            self.onStep("Creating the Python environment")
            self._runStep(venv, env)
            self.onStep(f"Downloading PyTorch ({self.backend.label})")
            self._runStep(sync, env)
            self.onStep("Checking PyTorch")
            probe = self._runStep(runtime.probeCommand(), runtime.workerEnv())
            runtime.writeManifest(self.backend, json.loads(probe.splitlines()[-1]))
            # The environment no longer needs uv's copies of the downloads;
            # on failure they stay, so a retry resumes.
            shutil.rmtree(runtime.root / "cache", ignore_errors=True)
        except BaseException:
            runtime.removeEnvironment()
            raise

    def _runStep(self, command: list[str], env: dict[str, str]) -> str:
        if self._cancelled.is_set():
            raise InstallCancelled("Install cancelled.")
        self.onLog("$ " + " ".join(command))
        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                creationflags=_NO_WINDOW,
            )
        except OSError as error:
            raise InstallError(f"Could not run {command[0]}: {error}") from error
        assert self._process.stdout is not None
        lines = []
        for line in self._process.stdout:
            lines.append(line.rstrip())
            self.onLog(lines[-1])
        code = self._process.wait()
        if self._cancelled.is_set():
            raise InstallCancelled("Install cancelled.")
        if code != 0:
            tail = "\n".join(lines[-15:])
            raise InstallError(f"{command[0]} exited with code {code}:\n{tail}")
        return "\n".join(lines)


def _bundledUv() -> list[str] | None:
    """The uv bundled with the app, or the developer's uv on PATH."""
    if getattr(sys, "frozen", False):
        name = "uv.exe" if sys.platform == "win32" else "uv"
        path = Path(resource_path(f"bin/{name}"))
        return [str(path)] if path.exists() else None
    found = shutil.which("uv")
    return [found] if found else None


def _workerDir() -> Path:
    """The folder whose ``varda_torch_worker`` package the environment imports.
    A dedicated folder in the bundle, so the app's own libraries stay hidden."""
    if getattr(sys, "frozen", False):
        return Path(resource_path("torch_worker"))
    return Path(varda_torch_worker.__file__).parents[1]


def defaultRuntime() -> TorchRuntime:
    folder = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return TorchRuntime(
        root=Path(folder) / "runtimes" / "torch",
        uv=_bundledUv() or [],
        workerDir=_workerDir(),
        lockDir=Path(resource_path("resources/optional_features/torch")),
    )
