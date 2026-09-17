"""The Run Analysis dialog picks an image and an analysis and shows its settings."""

from varda.analysis.analysis import Analysis
from varda.analysis.dialog import RunAnalysisDialog
from varda.common.parameter import IntParameter
from varda.utilities.debug import generate_random_image


class AlphaAnalysis(Analysis):
    name = "Alpha"
    description = "First test analysis."
    knob = IntParameter("Knob", 1, range=(0, 9))

    def run(self, image, reportProgress):
        return image


class BetaAnalysis(Analysis):
    name = "Beta"

    def run(self, image, reportProgress):
        return image


def test_dialog_lists_analyses_and_defaults_to_the_first(qtbot):
    images = [generate_random_image((10, 10, 10)) for _ in range(2)]
    dialog = RunAnalysisDialog(images, [AlphaAnalysis, BetaAnalysis])
    qtbot.addWidget(dialog)

    assert [dialog.analysisCombo.itemText(i) for i in range(2)] == ["Alpha", "Beta"]
    assert isinstance(dialog.selectedAnalysis(), AlphaAnalysis)
    assert dialog.selectedImage() is images[0]


def test_dialog_can_be_preselected(qtbot):
    images = [generate_random_image((10, 10, 10)) for _ in range(2)]
    dialog = RunAnalysisDialog(
        images, [AlphaAnalysis, BetaAnalysis], image=images[1], analysis=BetaAnalysis
    )
    qtbot.addWidget(dialog)

    assert isinstance(dialog.selectedAnalysis(), BetaAnalysis)
    assert dialog.selectedImage() is images[1]


def test_settings_follow_the_chosen_analysis_and_persist(qtbot):
    images = [generate_random_image((10, 10, 10))]
    dialog = RunAnalysisDialog(images, [AlphaAnalysis, BetaAnalysis])
    qtbot.addWidget(dialog)
    alpha = dialog.selectedAnalysis()
    assert isinstance(alpha, AlphaAnalysis)
    alpha.knob.set(7)

    dialog.analysisCombo.setCurrentIndex(1)
    assert isinstance(dialog.selectedAnalysis(), BetaAnalysis)
    dialog.analysisCombo.setCurrentIndex(0)

    assert dialog.selectedAnalysis() is alpha  # same instance, settings kept
    assert alpha.knob.value == 7


def test_accepting_emits_the_analysis_and_image(qtbot):
    images = [generate_random_image((10, 10, 10)) for _ in range(2)]
    dialog = RunAnalysisDialog(images, [AlphaAnalysis], image=images[1])
    qtbot.addWidget(dialog)
    received = []
    dialog.connectOnRun(lambda analysis, image: received.append((analysis, image)))

    dialog.accept()

    ((analysis, image),) = received
    assert isinstance(analysis, AlphaAnalysis)
    assert image is images[1]
