"""Every analysis's dialog fits a laptop screen: its settings scroll, and
nothing in it is cut off at its smallest width."""

import pytest

from varda.analysis.dialog import RunAnalysisDialog
from varda.analysis.registry import availableAnalyses
from varda.common.layout_audit import assertNothingClipped
from varda.utilities.debug import generate_random_image


@pytest.mark.parametrize("analysis", availableAnalyses(), ids=lambda a: a.name)
def test_an_analysis_dialog_fits_a_laptop_screen(qtbot, analysis):
    images = [generate_random_image((30, 30, 10)) for _ in range(2)]
    dialog = RunAnalysisDialog(images, [analysis], analysis=analysis, image=images[0])
    qtbot.addWidget(dialog)
    minimum = dialog.minimumSizeHint()
    assert minimum.width() <= 800 and minimum.height() <= 400
    dialog.resize(minimum.width(), 560)
    dialog.show()
    qtbot.waitExposed(dialog)
    assertNothingClipped(dialog)
