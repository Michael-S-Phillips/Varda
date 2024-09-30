"""
fileexplorer.py
"""
import PyQt6.QtGui as QtGui
import PyQt6.QtCore as QtCore
import PyQt6.QtWidgets as QtWidgets

import sys


class FileExplorer(QtWidgets.QWidget):
    def __init__(self):
        super(FileExplorer, self).__init__()
        self.fileModel = QtGui.QFileSystemModel()
        self.fileModel.setRootPath(QtCore.QDir.currentPath())
        self.treeView = QtWidgets.QTreeView()
        self.treeView.setModel(self.fileModel)
        self.treeView.setRootIndex(self.fileModel.index(QtCore.QDir.currentPath()))
        self.treeView.show()
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.treeView)
        self.setLayout(self.layout)
        self.fileName = None

        self.treeView.setDragEnabled(True)

        # button = QPushButton("Open File", self)
        # button.clicked.connect(self.open_file_dialog)
        #filePath = filedialog.askopenfilename(filetypes=[("ENVI Files", "*.hdr")])

    def openFileDialog(self):
        #upon clicking a file, send chosen image to spectral data viewer
        #overload _init_ to take the name of a file and display it
        options = QFileDialog()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;Text Files (*.txt)")
        if fileName:
            print(fileName)
            self.setFileName(fileName)

    def setFileName(self, fn):
        self.fileName = fn

    def getFileName(self):
        return self.fileName
