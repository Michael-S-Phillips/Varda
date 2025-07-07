from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit


class ROIStatisticsDialog(QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROI Statistics")
        text = QTextEdit(self)
        text.setReadOnly(True)

        # TODO: Setup a proper display format probably.
        text.setText(str(stats.getSummary()))
        layout = QVBoxLayout(self)
        layout.addWidget(text)
