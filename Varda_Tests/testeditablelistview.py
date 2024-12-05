import sys
import unittest

from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QModelIndex
from src.models.listmodel import ListModel
from src.gui.customwidgets.parameditor import EditableListView


class TestEditableListView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([])

    def setUp(self):
        self.model = ListModel([("Item1", "Value1"), ("Item2", "Value2", "Value3")])
        self.view = EditableListView(self.model)

    def test_editableListView_initializes_correctly(self):
        self.assertEqual(self.view.model, self.model)
        self.assertEqual(1, self.view.layout.count())
        self.assertEqual(4, self.view.formLayout.rowCount())

    def test_editableListView_populates_form_correctly(self):
        self.view.populateForm()
        self.assertEqual(4, self.view.formLayout.rowCount())
        self.assertEqual("Item1", self.view.formLayout.itemAt(0).widget().text())
        self.assertEqual("Item2", self.view.formLayout.itemAt(2).widget().text())

    def test_editableListView_updates_model_on_edit(self):
        self.view.populateForm()
        lineEdit = self.view.formLayout.itemAt(1).widget()
        lineEdit.setText("NewValue1")
        lineEdit.editingFinished.emit()
        self.assertEqual(
            self.model.data(self.model.index(0, 0), Qt.ItemDataRole.DisplayRole),
            ("Item1", "NewValue1"))

    def test_editableListView_handles_empty_model(self):
        empty_model = ListModel([])
        empty_view = EditableListView(empty_model)
        empty_view.populateForm()
        self.assertEqual(empty_view.formLayout.rowCount(), 0)

    def test_editableListView_handles_multiple_values(self):
        self.view.populateForm()
        lineEdit = self.view.formLayout.itemAt(3).widget()
        lineEdit.setText("NewValue3")
        lineEdit.editingFinished.emit()
        self.assertEqual(
            self.model.data(self.model.index(1, 0), Qt.ItemDataRole.DisplayRole),
            ("Item2", "Value2", "NewValue3"))


