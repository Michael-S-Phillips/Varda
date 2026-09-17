"""The Run dialog prepares the analysis for the chosen image and offers to save
the result to a file."""

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
