from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QFileDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.button = QPushButton("Open File", self)
        self.button.clicked.connect(self.open_file)

    def open_file(self):
        options = QFileDialog.options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", options=options)
        if fileName:
            print("Selected file:", fileName)

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()