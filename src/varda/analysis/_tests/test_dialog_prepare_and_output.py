"""The Run dialog prepares the analysis for the chosen image and offers to save
the result to a file."""

from PyQt6.QtWidgets import QLabel

from varda.analysis.analysis import Analysis
from varda.analysis.dialog import RunAnalysisDialog
from varda.common.parameter import IntParameter
from varda.utilities.debug import generate_random_image


class _RecordingAnalysis(Analysis):
    analysisId = "recording"
    name = "Recording"
    category = "Test"
    description = "records prepareFor calls"

    knob = IntParameter("Knob", 1, range=(0, 10))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preparedFor = []

    def prepareFor(self, image):
        self.preparedFor.append(image)


def test_dialog_prepares_the_analysis_for_the_initial_and_changed_image(qtbot):
    first, second = (
        generate_random_image((20, 20, 10)),
        generate_random_image((20, 20, 10)),
    )
    dialog = RunAnalysisDialog([first, second], [_RecordingAnalysis], image=first)
    qtbot.addWidget(dialog)
    analysis = dialog.selectedAnalysis()
    assert isinstance(analysis, _RecordingAnalysis)
    assert analysis.preparedFor == [first]

    dialog.imageParam.set(second)

    assert analysis.preparedFor == [first, second]


class _PickyAnalysis(_RecordingAnalysis):
    analysisId = "picky"
    name = "Picky"

    def unavailableReason(self, image):
        return "" if image.name == "ok" else "Picky needs an image named ok."

    def createPreviewWidget(self, image):
        return QLabel(f"preview of {image.name}")


def test_an_analysis_can_veto_the_image_with_a_reason(qtbot):
    good, bad = generate_random_image((20, 20, 10)), generate_random_image((20, 20, 10))
    good._name, bad._name = "ok", "nope"
    dialog = RunAnalysisDialog([good, bad], [_PickyAnalysis], image=bad)
    qtbot.addWidget(dialog)

    assert not dialog.runButton.isEnabled()
    assert dialog.statusLabel.text() == "Picky needs an image named ok."

    dialog.imageParam.set(good)
    assert dialog.runButton.isEnabled()
    assert dialog.statusLabel.text() == ""


class _KnobAnalysis(_RecordingAnalysis):
    analysisId = "knob"
    name = "Knob"
    # ParameterGroup only clones parameters defined on the concrete class
    knob = IntParameter("Knob", 1, range=(0, 10))

    def unavailableReason(self, image):
        return "" if self.knob.get() > 0 else "Turn the knob up first."


def test_run_state_follows_setting_changes(qtbot):
    image = generate_random_image((20, 20, 10))
    dialog = RunAnalysisDialog([image], [_KnobAnalysis], image=image)
    qtbot.addWidget(dialog)
    analysis = dialog.selectedAnalysis()
    assert isinstance(analysis, _KnobAnalysis)
    assert dialog.runButton.isEnabled()

    analysis.knob.set(0)
    assert not dialog.runButton.isEnabled()
    assert dialog.statusLabel.text() == "Turn the knob up first."

    analysis.knob.set(3)
    assert dialog.runButton.isEnabled()


def test_an_analysis_preview_is_shown_and_follows_the_image(qtbot):
    good, bad = generate_random_image((20, 20, 10)), generate_random_image((20, 20, 10))
    good._name, bad._name = "ok", "nope"
    dialog = RunAnalysisDialog([good, bad], [_PickyAnalysis], image=good)
    qtbot.addWidget(dialog)

    def previewText() -> str:
        preview = dialog.previewBox.content
        assert isinstance(preview, QLabel)
        return preview.text()

    assert previewText() == "preview of ok"
    dialog.imageParam.set(bad)
    assert previewText() == "preview of nope"


def test_analyses_without_a_preview_hide_the_preview_box(qtbot):
    image = generate_random_image((20, 20, 10))
    dialog = RunAnalysisDialog([image], [_RecordingAnalysis], image=image)
    qtbot.addWidget(dialog)
    assert dialog.previewBox.isHidden()


def test_output_path_is_none_unless_saving_is_enabled(qtbot):
    image = generate_random_image((20, 20, 10))
    dialog = RunAnalysisDialog([image], [_RecordingAnalysis], image=image)
    qtbot.addWidget(dialog)

    assert dialog.outputPath() is None
    dialog.pathEdit.setText("/tmp/out.img")
    assert dialog.outputPath() is None  # a path alone does not enable saving
    dialog.saveCheck.setChecked(True)
    assert dialog.outputPath() == "/tmp/out.img"


def test_run_is_disabled_while_saving_is_enabled_without_a_path(qtbot):
    image = generate_random_image((20, 20, 10))
    dialog = RunAnalysisDialog([image], [_RecordingAnalysis], image=image)
    qtbot.addWidget(dialog)

    dialog.saveCheck.setChecked(True)
    assert not dialog.runButton.isEnabled()
    assert "path" in dialog.statusLabel.text().lower()

    dialog.pathEdit.setText("/tmp/out.img")
    assert dialog.runButton.isEnabled()


def test_run_request_carries_the_output_path(qtbot):
    image = generate_random_image((20, 20, 10))
    dialog = RunAnalysisDialog([image], [_RecordingAnalysis], image=image)
    qtbot.addWidget(dialog)
    dialog.saveCheck.setChecked(True)
    dialog.pathEdit.setText("/tmp/out.img")
    requests = []
    dialog.connectOnRun(lambda *args: requests.append(args))

    dialog.accept()

    ((analysis, chosen, path),) = requests
    assert isinstance(analysis, _RecordingAnalysis)
    assert chosen is image
    assert path == "/tmp/out.img"
