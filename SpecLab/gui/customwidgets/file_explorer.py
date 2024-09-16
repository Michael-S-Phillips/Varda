"""
file_explorer.py
"""
from PyQt6.QtWidgets import QWidget, QFileDialog, QVBoxLayout, QTreeView
from PyQt6.QtCore import *
from . import BasicWidget
from PyQt6.QtGui import QFileSystemModel
import os
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
