from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLabel


class ROIStatisticsDialog(QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROI Statistics")
        label = QLabel("TODO: Present this data in a better way.", self)
        text = QTextEdit(self)
        text.setReadOnly(True)

        # TODO: Setup a proper display format probably.
        text.setText(str(stats.getSummary()))
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(text)
