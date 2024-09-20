"""
file_explorer.py
"""
from PyQt6.QtWidgets import QWidget, QFileDialog, QVBoxLayout, QTreeView, QPushButton
from PyQt6.QtCore import *
from . import BasicWidget
from PyQt6.QtGui import QFileSystemModel
import sys



class FileExplorer(BasicWidget):
    def __init__(self):
        super(FileExplorer, self).__init__()
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.currentPath())
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setRootIndex(self.file_model.index(QDir.currentPath()))
        self.tree_view.show()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tree_view)
        self.setLayout(self.layout)
        self.fileName = None


        button = QPushButton("Open File", self)
        button.clicked.connect(self.open_file_dialog)
        #file_path = filedialog.askopenfilename(filetypes=[("ENVI Files", "*.hdr")])

    def open_file_dialog(self):
        #upon clicking a file, send chosen image to spectral data viewer
        #overload _init_ to take the name of a file and display it
        options = QFileDialog()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;Text Files (*.txt)")
        if fileName:
            print(fileName)
            self.set_file_name(fileName)
        
    def set_file_name(self, fn):
        self.fileName = fn

    def get_file_name(self):
        return self.fileName
