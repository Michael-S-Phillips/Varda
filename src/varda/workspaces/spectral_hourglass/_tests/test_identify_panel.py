"""The identify panel ranks library spectra for the active endmember."""

import pytest

from synthetic_scene import WAVELENGTHS, endmemberSpectra, modelWithEndmembers
from varda.analysis.spectral_library import LibrarySpectrum
from varda.workspaces.spectral_hourglass.identify_panel import IdentifyPanel


def _library():
    E = endmemberSpectra()
    return [
        LibrarySpectrum("Flat Reference", WAVELENGTHS, E[0] * 1.1),
        LibrarySpectrum("Kaolinite KGa-1", WAVELENGTHS, E[1] * 0.9),
        LibrarySpectrum("Pyroxene", WAVELENGTHS, E[2] * 1.2),
    ]


@pytest.fixture
def panel(qtbot):
    model = modelWithEndmembers()
    widget = IdentifyPanel(model, library=_library())
    qtbot.addWidget(widget)
    return widget


def test_matches_for_the_active_endmember_are_ranked(panel):
    clay = panel.model.endmembers[1]
    panel.setEndmember(clay.id)
    assert panel.table.rowCount() == 3
    assert panel.table.item(0, 1).text() == "Kaolinite KGa-1"


def test_use_as_name_renames_the_endmember(panel):
    clay = panel.model.endmembers[1]
    panel.setEndmember(clay.id)
    panel.table.selectRow(0)
    panel.useNameButton.click()
    assert clay.name == "Kaolinite KGa-1"
    assert clay.identification.startswith("Kaolinite KGa-1")


def test_identify_all_records_each_best_match(panel):
    panel.identifyAllButton.click()
    identified = [e.identification.split(" (")[0] for e in panel.model.endmembers]
    assert identified == ["Flat Reference", "Kaolinite KGa-1", "Pyroxene"]


def test_double_clicking_a_match_previews_it(panel, qtbot):
    panel.setEndmember(panel.model.endmembers[2].id)
    with qtbot.waitSignal(panel.sigPreviewMatch) as blocker:
        panel.table.cellDoubleClicked.emit(0, 1)
    assert blocker.args[0].name == "Pyroxene"


def test_no_endmember_clears_the_table(panel):
    panel.setEndmember(None)
    assert panel.table.rowCount() == 0
