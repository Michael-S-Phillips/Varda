"""The app-managed PyTorch environment: hardware detection, install plan,
manifest, and running jobs in the worker."""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
import pytest

from varda.optional_features import torch_runtime
import varda_torch_worker
from varda_torch_worker import protocol
from varda.optional_features.torch_runtime import (
    BACKENDS,
    InstallCancelled,
    InstallError,
    Installer,
    TorchRuntime,
    detectBackend,
    platformBackends,
)

LOCKS = Path(__file__).parents[4] / "resources" / "optional_features" / "torch"


class _FakeRuntime(TorchRuntime):
    """A runtime whose interpreter (and optionally probe) are stand-ins."""

    python: Path | None = None
    probe: list[str] | None = None

    def pythonPath(self) -> Path:
        return self.python or super().pythonPath()

    def probeCommand(self) -> list[str]:
        return self.probe or super().probeCommand()


def _runtime(tmp_path, uv=("uv",), python=None, workerDir="/worker") -> _FakeRuntime:
    runtime = _FakeRuntime(
        root=tmp_path / "torch", uv=list(uv), workerDir=Path(workerDir), lockDir=LOCKS
    )
    runtime.python = Path(python) if python else None
    return runtime


def _manifest(runtime: TorchRuntime) -> dict:
    manifest = runtime.manifest()
    assert manifest is not None
    return manifest


@pytest.mark.parametrize(
    "system, machine, smi, expected",
    [
        ("Darwin", "arm64", None, "macos-arm64"),
        ("Darwin", "x86_64", None, None),  # no PyTorch for Intel Macs
        ("Linux", "x86_64", None, "linux-x64-cpu"),
        ("Linux", "x86_64", "590.10, 8.6, NVIDIA RTX A4000", "linux-x64-cu130"),
        (
            "Linux",
            "x86_64",
            "550.54, 8.6, NVIDIA RTX A4000",
            "linux-x64-cpu",
        ),  # old driver
        (
            "Windows",
            "AMD64",
            "581.15, 6.1, GeForce GTX 1080",
            "windows-x64-cpu",
        ),  # Pascal
        ("Windows", "AMD64", "581.15, 12.0, GeForce RTX 5090", "windows-x64-cu130"),
        ("Linux", "aarch64", None, None),
    ],
)
def test_detection_picks_the_build_for_the_hardware(system, machine, smi, expected):
    backend = detectBackend(system, machine, lambda: smi)
    assert (backend.key if backend else None) == expected


def test_every_backend_has_a_lock_and_a_measured_download(tmp_path):
    runtime = _runtime(tmp_path)
    for backend in BACKENDS.values():
        assert (LOCKS / f"{backend.key}.txt").is_file()
        assert 100 < runtime.downloadMB(backend) < 5000


def test_the_choices_match_the_platform():
    keys = [b.key for b in platformBackends("Windows", "AMD64")]
    assert keys == ["windows-x64-cpu", "windows-x64-cu130"]
    assert platformBackends("Darwin", "x86_64") == []


def test_the_install_plan_creates_an_isolated_env_and_syncs_the_hashed_lock(tmp_path):
    runtime = _runtime(tmp_path)
    venv, sync = runtime.installCommands(BACKENDS["linux-x64-cu130"])
    assert venv[:2] == ["uv", "venv"] and str(runtime.envDir) in venv
    assert "--python-preference" in venv and "only-managed" in venv
    assert sync[:3] == ["uv", "pip", "sync"]
    assert str(LOCKS / "linux-x64-cu130.txt") in sync
    assert "--require-hashes" in sync
    assert sync[sync.index("--torch-backend") + 1] == "cu130"
    assert "--torch-backend" not in runtime.installCommands(BACKENDS["macos-arm64"])[1]
    env = runtime.installEnv()
    assert env["UV_CACHE_DIR"] == str(runtime.root / "cache")
    assert env["UV_PYTHON_INSTALL_DIR"] == str(runtime.root / "python")
    assert env["UV_NO_CONFIG"] == "1"


def test_the_worker_env_sees_only_the_worker_code(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    monkeypatch.setenv("PYTHONHOME", "/conda")
    env = _runtime(tmp_path).workerEnv()
    assert env["PYTHONPATH"] == "/worker"
    assert "PYTHONHOME" not in env and env["PYTHONNOUSERSITE"] == "1"


def test_installed_only_with_a_manifest_and_an_interpreter(tmp_path):
    runtime = _runtime(tmp_path, python=sys.executable)
    assert not runtime.isInstalled() and runtime.manifest() is None
    backend = BACKENDS["macos-arm64"]
    runtime.writeManifest(backend, {"torch": "2.14.1", "device": "mps"})
    assert runtime.isInstalled()
    manifest = _manifest(runtime)
    assert manifest["backend"] == "macos-arm64" and manifest["torch"] == "2.14.1"
    assert not runtime.updateAvailable()
    (runtime.root / "manifest.json").write_text(
        json.dumps({**manifest, "lockSha256": "old"})
    )
    assert runtime.isInstalled() and runtime.updateAvailable()
    runtime.uninstall()
    assert not runtime.root.exists() and not runtime.isInstalled()


def _fakeUv(tmp_path: Path, body: str) -> list[str]:
    script = tmp_path / "fake_uv.py"
    script.write_text(body)
    return [sys.executable, str(script)]


def test_the_installer_runs_each_step_logs_output_and_writes_the_manifest(tmp_path):
    uv = _fakeUv(tmp_path, "import sys; print('ran', ' '.join(sys.argv[1:3]))")
    runtime = _runtime(tmp_path, uv=uv, python=sys.executable)
    (runtime.root / "cache").mkdir(parents=True)
    runtime.probe = [  # the probe must see the worker code, not uv's environment
        sys.executable,
        "-c",
        "import json, os; assert os.environ['PYTHONPATH'] == '/worker';"
        " print(json.dumps({'torch': '2.14.1', 'device': 'cpu'}))",
    ]
    lines, steps = [], []
    Installer(runtime, BACKENDS["linux-x64-cpu"], lines.append, steps.append).run()
    assert any("ran venv" in line for line in lines)
    assert any("ran pip sync" in line for line in lines)
    assert len(steps) == 3
    assert _manifest(runtime)["device"] == "cpu"
    assert not (runtime.root / "cache").exists()  # the downloads are cleared


def test_a_failed_step_raises_and_leaves_nothing_half_installed(tmp_path):
    uv = _fakeUv(tmp_path, "import sys; print('no network'); sys.exit(2)")
    runtime = _runtime(tmp_path, uv=uv, python=sys.executable)
    with pytest.raises(InstallError, match="no network"):
        Installer(
            runtime, BACKENDS["linux-x64-cpu"], lambda _: None, lambda _: None
        ).run()
    assert not runtime.envDir.exists() and runtime.manifest() is None


def test_cancelling_stops_the_running_step(tmp_path):
    uv = _fakeUv(tmp_path, "import time; print('working', flush=True); time.sleep(30)")
    runtime = _runtime(tmp_path, uv=uv, python=sys.executable)
    installer = Installer(
        runtime, BACKENDS["linux-x64-cpu"], lambda _: installer.cancel(), lambda _: None
    )
    with pytest.raises(InstallCancelled):
        installer.run()
    assert runtime.manifest() is None


def test_a_job_runs_in_the_worker_process(tmp_path):
    pytest.importorskip("torch")
    import varda_torch_worker

    runtime = _runtime(
        tmp_path,
        python=sys.executable,
        workerDir=Path(varda_torch_worker.__file__).parents[1],
    )
    rng = np.random.default_rng(0)
    cube = rng.normal(size=(6, 8, 3)).astype(np.float32)
    valid = np.ones((6, 8), dtype=bool)
    spec = {
        "model": "cnn",
        "patchSize": 3,
        "epochs": 2,
        "learningRate": 1e-2,
        "batchSize": 8,
        "modelParams": {"channels": 4, "convLayers": 1},
    }
    progress = []
    probabilities, info = runtime.runJob(
        cube,
        valid,
        np.array([1, 4]),
        np.array([1, 6]),
        np.array([0, 1]),
        classes=2,
        spec=spec,
        progress=lambda f, m: progress.append(f),
    )
    assert probabilities.shape == (48, 2) and progress[-1] == 1.0
    with pytest.raises(RuntimeError, match="Unknown model"):
        runtime.runJob(
            cube,
            valid,
            np.array([1, 4]),
            np.array([1, 6]),
            np.array([0, 1]),
            classes=2,
            spec={**spec, "model": "nope"},
            progress=lambda f, m: None,
        )


def test_the_default_runtime_lives_in_the_app_data_folder():
    runtime = torch_runtime.defaultRuntime()
    assert runtime.root.parts[-2:] == ("runtimes", "torch")


def test_match_jobs_round_trip(tmp_path):
    reference = np.arange(12, dtype=np.float32).reshape(3, 4)
    protocol.writeMatchJob(tmp_path, reference, reference + 1, "loftr")
    assert protocol.jobTask(tmp_path)["task"] == "match"
    loaded, moving, method = protocol.readMatchJob(tmp_path)
    assert method == "loftr" and np.array_equal(loaded, reference)
    protocol.writeMatches(tmp_path, np.ones((2, 5)))
    assert protocol.readMatches(tmp_path).shape == (2, 5)


def test_a_match_runs_in_the_worker_and_relays_progress(tmp_path):
    """runMatch's plumbing, with a stand-in interpreter for the worker."""
    fake = tmp_path / "python"
    fake.write_text(
        f"""#!{sys.executable}
import json, sys
import numpy as np
job = sys.argv[-1]
print(json.dumps({{"progress": 0.5, "message": "matching"}}), flush=True)
np.save(job + "/matches.npy", np.array([[1, 2, 6, 0, 0.9]], np.float32))
"""
    )
    fake.chmod(0o755)
    runtime = _runtime(tmp_path, python=str(fake))
    seen = []
    first, second, confidence = runtime.runMatch(
        np.zeros((4, 4)), np.zeros((4, 4)), "sift", lambda f, m: seen.append(m)
    )
    assert seen == ["matching"]
    assert np.allclose(second - first, [[5, -2]]) and np.allclose(confidence, 0.9)
    assert runtime.workerEnv()["TORCH_HOME"] == str(runtime.root / "hub")


def test_sift_matches_a_shift_in_the_worker(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("kornia")
    pytest.importorskip("cv2")
    runtime = _runtime(
        tmp_path,
        python=sys.executable,
        workerDir=Path(varda_torch_worker.__file__).parents[1],
    )
    rng = np.random.default_rng(0)
    texture = ndimage.gaussian_filter(rng.normal(size=(300, 300)), 2.0).astype(
        np.float32
    )
    first, second, _ = runtime.runMatch(
        texture[20:220, 20:220], texture[23:223, 15:215], "sift"
    )
    assert len(first) > 10
    assert np.allclose(np.median(second - first, axis=0), [5, -3], atol=0.5)
