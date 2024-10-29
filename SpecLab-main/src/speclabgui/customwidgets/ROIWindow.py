from PyQt6.QtWidgets import QApplication, QMainWindow, \
QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, \
QWidget, QMessageBox, QDialog
from PyQt6.QtCore import Qt

'''
Subclass of SpectralMainImageDisplay
Will create a popup window that display information about saved ROIs
User can add notes, see mean / std of a spectral plot, and select an
ROI they want to view on the image display
'''

color_keys = ['blue', 'green', 'red', 'cyan', 'magenta', 'yellow', 'white']

class ROIWindow(QDialog):
    def __init__(self, imageView, rois):
        super().__init__(imageView)
        self.imageView = imageView
        self.rois = rois

        self.table = QTableWidget(self)
        self.table.setRowCount(len(self.rois))
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["     ROI ID     ", "     Color     ", 
            "     Notes     ", "     Mean Spectrum Plot     ", "     Std Spectrum Plot     "])

        for col in range(self.table.columnCount()):
            self.table.resizeColumnToContents(col)

        for (row, roi) in enumerate(self.rois):
            self.table.setItem(row, 0, QTableWidgetItem("ROI: " + str(row)))
            self.table.setItem(row, 1, QTableWidgetItem(color_keys[row]))
            self.table.setItem(row, 2, QTableWidgetItem(" "))
            self.table.setCellWidget(row, 3, QPushButton("Load Spec", self))
            self.table.setCellWidget(row, 4, QPushButton("Load Spec", self))

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.selectedROI)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.setWindowTitle("Session ROIs")
        self.resize(800, 400)
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | 
                             Qt.WindowType.WindowStaysOnTopHint)

    def selectedROI(self):
        curr_row = self.table.currentRow()
        if curr_row > -1:
            self.imageView.loadROIState(curr_row)



