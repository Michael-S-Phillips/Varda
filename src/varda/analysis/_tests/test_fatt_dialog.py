"""The FATT window ranks library targets and sets up a detection map."""

import numpy as np
import pytest
from PyQt6.QtCore import Qt

from varda.analysis.fatt_dialog import FattDialog
from varda.analysis.fatt_map import FattMapAnalysis
from varda.analysis.spectral_library import LibrarySpectrum
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WAVELENGTHS = np.linspace(1000.0, 2600.0, 160)


def _spectrum(continuum: float, *bands: tuple[float, float, float]) -> np.ndarray:
    s = continuum + 0.05 * (WAVELENGTHS - 1000.0) / 1600.0
    for center, width, depth in bands:
        s = s * (1 - depth * np.exp(-0.5 * ((WAVELENGTHS - center) / width) ** 2))
    return s


SCENE = {
    "kaolinite": _spectrum(0.45, (2165, 12, 0.25), (2205, 14, 0.35)),
    "nontronite": _spectrum(0.35, (2285, 18, 0.3), (2400, 25, 0.15)),
    "olivine": _spectrum(0.25),
}
DECOYS = {"calcite": _spectrum(0.4, (2340, 22, 0.35))}


@pytest.fixture
def dialog(qtbot):
    rng = np.random.default_rng(0)
    cube = rng.dirichlet(np.ones(3), size=(40, 40)) @ np.stack(list(SCENE.values()))
    cube += rng.normal(scale=5e-4, size=cube.shape)
    image = VardaRaster(
        ArrayDataSource(
            cube.astype(np.float32), wavelengths=WAVELENGTHS, wavelengthUnits="nm"
        ),
        name="scene",
    )
    library = [LibrarySpectrum(n, WAVELENGTHS, s) for n, s in (SCENE | DECOYS).items()]
    widget = FattDialog([image], library=library)
    qtbot.addWidget(widget)
    return widget


def _analyze(dialog, qtbot):
    dialog.analyze()
    qtbot.waitUntil(lambda: dialog.factors is not None, timeout=10000)


def test_the_default_range_is_the_crism_window(dialog):
    assert (dialog.minWavelength.get(), dialog.maxWavelength.get()) == (1700.0, 2600.0)


def test_analyze_suggests_factors_and_ranks_the_scene_minerals_first(dialog, qtbot):
    _analyze(dialog, qtbot)
    assert dialog.factorCount.get() == 3
    top = {dialog.table.item(row, 1).text() for row in range(3)}
    assert top == set(SCENE)
    assert dialog.table.item(3, 1).text() == "calcite"


def test_changing_the_factor_count_reranks(dialog, qtbot):
    _analyze(dialog, qtbot)
    before = dialog._fits[0].nrmse
    dialog.factorCount.set(1)
    assert dialog._fits[0].nrmse > before


def test_the_filter_hides_other_targets(dialog, qtbot):
    _analyze(dialog, qtbot)
    dialog.filterEdit.setText("kao")
    shown = [
        r for r in range(dialog.table.rowCount()) if not dialog.table.isRowHidden(r)
    ]
    assert [dialog.table.item(r, 1).text() for r in shown] == ["kaolinite"]


def test_ticked_targets_set_up_the_detection_map(dialog, qtbot):
    _analyze(dialog, qtbot)
    assert not dialog.mapButton.isEnabled()
    for row in range(dialog.table.rowCount()):
        if dialog.table.item(row, 1).text() in ("kaolinite", "calcite"):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
    assert dialog.mapButton.text() == "Map 2 Ticked Targets…"
    dialog.threshold.set(0.5)

    with qtbot.waitSignal(dialog.sigMapRequested) as blocker:
        dialog.mapButton.click()
    image, analysis = blocker.args
    assert image.name == "scene"
    assert isinstance(analysis, FattMapAnalysis)
    assert sorted(t.name for t in analysis.targets) == ["calcite", "kaolinite"]
    assert analysis.threshold.get() == 0.5
    assert analysis.minWavelength.get() == 1700.0
