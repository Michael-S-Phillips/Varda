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
    def __init__(self, imageWorkspace, rois):
        super().__init__(imageWorkspace.mainImage)
        self.workspace = imageWorkspace
        self.imageView = imageWorkspace.mainImage
        self.rois = rois

        self.table = QTableWidget(self)
        self.create_table()
        
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
        self.finished.connect(self.onClose)

    def create_table(self):
        # creating the table with roi elements
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
            currMean = QPushButton("Load Mean")
            currStd = QPushButton("Load Std")
            currMean.clicked.connect(self.getMeanPlot)
            currStd.clicked.connect(self.getStdPlot)
            self.table.setCellWidget(row, 3, currMean)
            self.table.setCellWidget(row, 4, currStd)


    def selectedROI(self):
        curr_row = self.table.currentRow()
        if curr_row > -1:
            self.workspace.loadROIState(curr_row)


    def getMeanPlot(self):
        # creating mean plot in workspace
        button = self.sender()
        if button:
            for row in range(self.table.rowCount()):
                if self.table.cellWidget(row, 3) == button:
                    self.workspace.loadMeanPlot(self.rois[row])
                    return row

    def getStdPlot(self):
        # creating std plot in worksapce
        button = self.sender()
        if button:
            for row in range(self.table.rowCount()):
                if self.table.cellWidget(row, 4) == button:
                    self.workspace.loadStdPlot(self.rois[row])
                    return row
    
    def onClose(self):
        # ensuring that multiple instances of roiWindow are not created
        self.workspace.roiWind = None

    def updateROIs(self, new_rois):
        # updating the table with new ROIs that have been created 
        self.rois = new_rois
        self.create_table()

