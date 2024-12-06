import sys

from PyQt6 import QtWidgets

from src.models.listmodel import ListModel

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # Remove external stylesheet to revert to default Qt styling
    model = ListModel([("Item1", "Value1"), ("Item2", "Value2", "Value3")])
    view = EditableListView(model)
    view.show()
    app.exec()
