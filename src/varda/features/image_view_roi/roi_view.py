import logging
from typing import Any, NamedTuple

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMenu,
    QHeaderView,
    QLabel,
    QCheckBox,
    QColorDialog,
    QInputDialog,
    QMessageBox,
    QSplitter,
    QLineEdit,
    QGroupBox,
    QFormLayout,
    QSlider,
    QDialog,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QAction

from varda.core.entities import ROI
from .roi_viewmodel import ROIViewModel


logger = logging.getLogger(__name__)


class ROITableColumn(NamedTuple):
    """Represents a column in the ROI table with display settings"""

    name: str
    visible: bool = True
    width: int = 100
    editable: bool = True


class ROITableWidget(QTableWidget):
    """Table widget for displaying and managing ROIs"""

    roiSelectionChanged = pyqtSignal(int)  # Emits ROI index when selection changes
    roiDoubleClicked = pyqtSignal(int)  # Emits ROI index when double-clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.itemSelectionChanged.connect(self.onSelectionChanged)
        self.cellDoubleClicked.connect(self.onCellDoubleClicked)

        # Set up right-click menu
        self.contextMenu = QMenu(self)
        self.setupContextMenu()

    def setupContextMenu(self):
        """Set up the right-click context menu"""
        self.actionShowHide = QAction("Toggle Visibility", self)
        self.actionPlot = QAction("Plot Spectrum", self)
        self.actionRemove = QAction("Remove ROI", self)
        self.actionRename = QAction("Rename ROI", self)
        self.actionChangeColor = QAction("Change Color", self)

        self.contextMenu.addAction(self.actionShowHide)
        self.contextMenu.addAction(self.actionPlot)
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(self.actionRename)
        self.contextMenu.addAction(self.actionChangeColor)
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(self.actionRemove)

        # Connect actions
        self.actionShowHide.triggered.connect(self.onToggleVisibility)
        self.actionPlot.triggered.connect(self.onPlotSpectrum)
        self.actionRemove.triggered.connect(self.onRemoveROI)
        self.actionRename.triggered.connect(self.onRenameROI)
        self.actionChangeColor.triggered.connect(self.onChangeColor)

    def showContextMenu(self, pos):
        """Show the context menu at the given position"""
        # Only show if a row is selected
        if self.selectedItems():
            self.contextMenu.popup(self.viewport().mapToGlobal(pos))

    def onSelectionChanged(self):
        """Handle selection changes in the table"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.roiSelectionChanged.emit(row)

    def onCellDoubleClicked(self, row, column):
        """Handle double-click on a cell"""
        self.roiDoubleClicked.emit(row)

    def onToggleVisibility(self):
        """Toggle visibility of the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().toggleRoiVisibility(row)

    def onPlotSpectrum(self):
        """Plot the spectrum of the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().plotRoiSpectrum(row)

    def onRemoveROI(self):
        """Remove the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().removeRoi(row)

    def onRenameROI(self):
        """Rename the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().renameRoi(row)

    def onChangeColor(self):
        """Change the color of the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().changeRoiColor(row)


class ROIPropertyEditor(QWidget):
    """Widget for editing ROI properties"""

    propertyChanged = pyqtSignal(int, str, object)  # ROI index, property name, value

    def __init__(self, roiManager, parent=None):
        super().__init__(parent)
        self.roiManager = roiManager
        self.currentRoiIndex = None

        layout = QVBoxLayout()

        # Name
        nameLayout = QHBoxLayout()
        nameLayout.addWidget(QLabel("Name:"))
        self.nameEdit = QLineEdit()
        self.nameEdit.textChanged.connect(
            lambda text: self.onPropertyChanged("name", text)
        )
        nameLayout.addWidget(self.nameEdit)
        layout.addLayout(nameLayout)

        # Color
        colorLayout = QHBoxLayout()
        colorLayout.addWidget(QLabel("Color:"))
        self.colorButton = QPushButton()
        self.colorButton.setFixedSize(24, 24)
        self.colorButton.clicked.connect(self.onChangeColor)
        colorLayout.addWidget(self.colorButton)
        layout.addLayout(colorLayout)

        # Opacity (simulated with alpha value)
        opacityLayout = QHBoxLayout()
        opacityLayout.addWidget(QLabel("Opacity:"))
        self.opacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(0, 100)
        self.opacitySlider.setValue(50)
        self.opacitySlider.valueChanged.connect(
            lambda value: self.onPropertyChanged("opacity", value / 100.0)
        )
        opacityLayout.addWidget(self.opacitySlider)
        layout.addLayout(opacityLayout)

        # Visibility (simulated)
        visibilityLayout = QHBoxLayout()
        self.visibleCheckbox = QCheckBox("Visible")
        self.visibleCheckbox.setChecked(True)
        self.visibleCheckbox.toggled.connect(
            lambda checked: self.onPropertyChanged("visible", checked)
        )
        visibilityLayout.addWidget(self.visibleCheckbox)
        layout.addLayout(visibilityLayout)

        # Information
        infoGroup = QGroupBox("Information")
        infoLayout = QFormLayout()
        self.pointsLabel = QLabel("0")
        infoLayout.addRow("Points:", self.pointsLabel)
        self.imageIndexLabel = QLabel("0")
        infoLayout.addRow("Image Index:", self.imageIndexLabel)
        infoGroup.setLayout(infoLayout)
        layout.addWidget(infoGroup)

        # Statistics
        statsGroup = QGroupBox("Statistics")
        statsLayout = QFormLayout()
        self.meanLabel = QLabel("N/A")
        statsLayout.addRow("Mean Value:", self.meanLabel)
        self.stdLabel = QLabel("N/A")
        statsLayout.addRow("Std Deviation:", self.stdLabel)
        statsGroup.setLayout(statsLayout)
        layout.addWidget(statsGroup)

        # Add stretch at the bottom
        layout.addStretch()

        self.setLayout(layout)
        self.setEnabled(False)  # Disable until an ROI is selected

    def setRoi(self, roi: ROI, index: int):
        """Set the ROI to edit"""
        if roi is None:
            self.currentRoiIndex = None
            self.setEnabled(False)
            return

        self.currentRoiIndex = index
        self.setEnabled(True)

        # Block signals during updates
        self.blockSignals(True)

        self.nameEdit.setText(f"ROI {index}")
        self.updateColorButton(roi.color)
        self.opacitySlider.setValue(50)  # Default 50% opacity
        self.visibleCheckbox.setChecked(True)  # Default visible

        # Update information
        if roi.points is not None:
            self.pointsLabel.setText(
                str(len(roi.points[0]))
            )  # Points is a list of two lists [x_values, y_values]
        else:
            self.pointsLabel.setText("0")

        self.imageIndexLabel.setText(str(self.roiManager.getImagesForROI(roi.id)[0]))

        # Update statistics if available
        if roi.meanSpectrum is not None:
            meanValue = float(roi.meanSpectrum.mean())
            self.meanLabel.setText(f"{meanValue:.4f}")

            # Std is not available in the current ROI class, so we'll set a placeholder
            self.stdLabel.setText("N/A")
        else:
            self.meanLabel.setText("N/A")
            self.stdLabel.setText("N/A")

        self.blockSignals(False)

    def updateColorButton(self, color):
        """Update the color button with the given color"""
        if isinstance(color, str):
            qcolor = QColor(color)
        else:  # Assume tuple/list of RGB or RGBA
            if len(color) == 3:
                r, g, b = color
                qcolor = QColor(r, g, b)
            else:
                r, g, b, a = color
                qcolor = QColor(r, g, b, a)

        style = f"background-color: {qcolor.name()}"
        self.colorButton.setStyleSheet(style)

    def onChangeColor(self):
        """Open a color dialog to change the ROI color"""
        if self.currentRoiIndex is None:
            return

        initialColor = self.colorButton.palette().button().color()
        color = QColorDialog.getColor(
            initial=initialColor, parent=self, title="Select ROI Color"
        )

        if color.isValid():
            self.updateColorButton(color.name())
            self.onPropertyChanged("color", color.name())

    def onPropertyChanged(self, propertyName: str, value: Any):
        """Emit a signal when a property is changed"""
        if self.currentRoiIndex is not None and not self.signalsBlocked():
            self.propertyChanged.emit(self.currentRoiIndex, propertyName, value)


class ROIColumnManager(QDialog):
    """Dialog for managing which columns are displayed in the ROI table"""

    columnsChanged = pyqtSignal(list)  # Emits list of visible column names

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Columns")
        self.columns = columns.copy()  # Make a copy to avoid modifying the original

        layout = QVBoxLayout()

        # Create a list widget for the columns
        self.columnList = QListWidget()
        for column in self.columns:
            item = QListWidgetItem(column.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if column.visible else Qt.CheckState.Unchecked
            )
            self.columnList.addItem(item)

        layout.addWidget(self.columnList)

        # Buttons
        buttonLayout = QHBoxLayout()
        self.okButton = QPushButton("OK")
        self.okButton.clicked.connect(self.accept)
        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.reject)

        buttonLayout.addStretch()
        buttonLayout.addWidget(self.okButton)
        buttonLayout.addWidget(self.cancelButton)

        layout.addLayout(buttonLayout)

        self.setLayout(layout)

    def getVisibleColumns(self):
        """Get the list of columns with updated visibility"""
        result = []
        for i in range(self.columnList.count()):
            item = self.columnList.item(i)
            column = self.columns[i]
            result.append(
                ROITableColumn(
                    name=column.name,
                    visible=item.checkState() == Qt.CheckState.Checked,
                    width=column.width,
                    editable=column.editable,
                )
            )
        return result


class ROIView(QWidget):
    """View for ROI management"""

    roiSelectionChanged = pyqtSignal(int)  # Emits ROI index when selection changes

    def __init__(self, viewModel: ROIViewModel, parent=None):
        super().__init__(parent)
        self.viewModel = viewModel
        self.viewModel.setView(self)  # Set reference to this view in the viewModel
        self.selectedRoiIndex = None

        # Define default columns
        self.columns = [
            ROITableColumn("Index", True, 60, False),
            ROITableColumn("Color", True, 60, False),
            ROITableColumn("Points", True, 60, False),
            ROITableColumn("Geospatial Points", True, 120, False),
            ROITableColumn("Image Index", True, 80, False),
            ROITableColumn("Mean Spectrum", True, 120, False),
            ROITableColumn("Actions", True, 120, False),
        ]

        self.initUI()
        self.connectSignals()
        self.updateROITable()

    def getDisplayController(self):
        """Get the ROI display controller for external viewport registration"""
        return self.viewModel.getDisplayController()

    def initUI(self):
        """Initialize the UI"""
        mainLayout = QVBoxLayout()

        # Header with buttons
        headerLayout = QHBoxLayout()

        self.showAllButton = QPushButton("Show All", self)
        self.showAllButton.setToolTip("Show all ROIs")
        headerLayout.addWidget(self.showAllButton)

        self.hideAllButton = QPushButton("Hide All", self)
        self.hideAllButton.setToolTip("Hide all ROIs")
        headerLayout.addWidget(self.hideAllButton)

        self.blinkButton = QPushButton("Blink", self)
        self.blinkButton.setCheckable(True)
        self.blinkButton.setToolTip("Toggle blinking of ROIs")
        headerLayout.addWidget(self.blinkButton)

        headerLayout.addStretch()

        # Column management
        self.manageColumnsButton = QPushButton("Manage Columns", self)
        self.manageColumnsButton.setToolTip("Manage which columns are displayed")
        headerLayout.addWidget(self.manageColumnsButton)

        mainLayout.addLayout(headerLayout)

        # Status label for feedback
        self.statusLabel = QLabel("Ready")
        mainLayout.addWidget(self.statusLabel)

        # Splitter for table and properties
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ROI Table
        self.roiTable = ROITableWidget(self)
        self.setupROITable()
        splitter.addWidget(self.roiTable)

        # Property editor
        self.propertyEditor = ROIPropertyEditor(self.viewModel.proj.roiManager)
        splitter.addWidget(self.propertyEditor)

        # Set initial sizes
        splitter.setSizes([int(self.width() * 0.7), int(self.width() * 0.3)])

        mainLayout.addWidget(splitter, 1)  # Give the splitter stretch

        self.setLayout(mainLayout)

    def setupROITable(self):
        """Set up the ROI table with columns"""
        visibleColumns = [col for col in self.columns if col.visible]
        self.roiTable.setColumnCount(len(visibleColumns))
        headerLabels = [col.name for col in visibleColumns]
        self.roiTable.setHorizontalHeaderLabels(headerLabels)

        # Set column widths
        for i, col in enumerate(visibleColumns):
            self.roiTable.setColumnWidth(i, col.width)

        # Set table properties
        self.roiTable.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.roiTable.horizontalHeader().setStretchLastSection(True)

    def connectSignals(self):
        """Connect UI signals"""
        self.showAllButton.clicked.connect(self.showAllROIs)
        self.hideAllButton.clicked.connect(self.hideAllROIs)
        self.blinkButton.clicked.connect(self.toggleBlinkROIs)
        self.manageColumnsButton.clicked.connect(self.showManageColumnsDialog)

        self.roiTable.roiSelectionChanged.connect(self.onRoiSelectionChanged)
        self.roiTable.roiDoubleClicked.connect(self.onRoiDoubleClicked)

        self.propertyEditor.propertyChanged.connect(self.onRoiPropertyChanged)

        # Connect ViewModel signals
        self.viewModel.roiAdded.connect(self.onRoiAdded)
        self.viewModel.roiRemoved.connect(self.onRoiRemoved)
        self.viewModel.roiUpdated.connect(self.onRoiUpdated)

    def updateROITable(self, rois=None):
        """Update the ROI table with current data"""
        if rois is None:
            rois = self.viewModel.getROIs(imageIndex=self.viewModel.imageIndex)

        # Clear the table
        self.roiTable.setRowCount(0)

        # Add the rows
        for i, roi in enumerate(rois):

            self.roiTable.insertRow(i)

            visibleColumns = [col for col in self.columns if col.visible]
            for j, col in enumerate(visibleColumns):
                item = self.createTableItem(roi, col.name, i)
                if item:
                    if not col.editable:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.roiTable.setItem(i, j, item)

        # If a ROI was selected, try to reselect it
        if self.selectedRoiIndex is not None and self.selectedRoiIndex < len(rois):
            self.roiTable.selectRow(self.selectedRoiIndex)

    def createTableItem(self, roi, columnName, roiIndex):
        """Create a table item for the given ROI and column"""
        item = QTableWidgetItem()

        # Set the value based on column type - reading directly from ROI entity
        if columnName == "Index":
            item.setText(str(roiIndex))
        elif columnName == "Color":
            item.setText("")
            # Use the ROI's actual color property
            color = roi.color
            item.setBackground(QBrush(QColor(color.red(), color.green(), color.blue())))
        elif columnName == "Points":
            if roi.points is not None:
                item.setText(str(len(roi.points)))
            else:
                item.setText("0")
        elif columnName == "Geospatial Points":
            if roi.geoPoints is not None:
                item.setText(str(len(roi.geoPoints)))
            else:
                item.setText("Not available")
        elif columnName == "Image Index":
            item.setText(str(roi.sourceImageIndex))
        elif columnName == "Mean Spectrum":
            if roi.meanSpectrum is not None:
                item.setText("Available")
            else:
                item.setText("Not calculated")
        elif columnName == "Actions":
            # For actions column, we would typically create a widget with buttons
            # But QTableWidgetItem doesn't support widgets directly
            # For now, just add text indicating actions are available
            item.setText("Plot | Export")

        return item

    def showAllROIs(self):
        """Show all ROIs"""
        self.viewModel.showAllROIs()
        self.statusLabel.setText("All ROIs visible")

    def hideAllROIs(self):
        """Hide all ROIs"""
        self.viewModel.hideAllROIs()
        self.statusLabel.setText("All ROIs hidden")

    def toggleBlinkROIs(self, checked):
        """Toggle ROI blinking"""
        if checked:
            self.viewModel.startBlinking()
            self.statusLabel.setText("ROI blinking enabled")
        else:
            self.viewModel.stopBlinking()
            self.statusLabel.setText("ROI blinking disabled")

    def showManageColumnsDialog(self):
        """Show the manage columns dialog"""
        dialog = ROIColumnManager(self.columns, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.columns = dialog.getVisibleColumns()
            self.setupROITable()
            self.updateROITable()

    def onRoiSelectionChanged(self, roiIndex):
        """Handle ROI selection change"""
        if roiIndex >= 0 and roiIndex < len(
            self.viewModel.getROIs(self.viewModel.imageIndex)
        ):
            self.selectedRoiIndex = roiIndex
            rois = self.viewModel.getROIs(self.viewModel.imageIndex)
            if roiIndex < len(rois):
                roi = rois[roiIndex]
                self.propertyEditor.setRoi(roi, roiIndex)
                self.roiSelectionChanged.emit(roiIndex)

                # Highlight the ROI through the ViewModel
                self.viewModel.highlightRoi(roi.id)

    def onRoiDoubleClicked(self, roiIndex):
        """Handle ROI double-click"""
        self.plotRoiSpectrum(roiIndex)

    def onRoiPropertyChanged(self, roiIndex, propertyName, value):
        """Handle property change from property editor"""
        rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        if roiIndex < len(rois):
            roi = rois[roiIndex]

            # Update through ViewModel
            if propertyName == "color":
                color = QColor(value) if isinstance(value, str) else value
                self.viewModel.updateRoi(roi.id, color=color)
            elif propertyName == "visible":
                self.viewModel.updateRoiVisibility(roi.id, value)
            elif propertyName == "opacity":
                self.viewModel.updateRoi(roi.id, opacity=value)

    def toggleRoiVisibility(self, roiIndex):
        """Toggle visibility of an ROI"""
        rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        if roiIndex < len(rois):
            roi = rois[roiIndex]
            currentVisibility = self.viewModel.getDisplayController().getRoiVisibility(
                roi.id
            )
            self.viewModel.updateRoiVisibility(roi.id, not currentVisibility)

    def plotRoiSpectrum(self, roiIndex):
        """Plot the spectrum of an ROI"""
        rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        if roiIndex < len(rois):
            roi = rois[roiIndex]
            self.viewModel.plotRoiSpectrum(roi.id)

    def removeRoi(self, roiIndex):
        """Remove an ROI"""
        confirm = QMessageBox.question(
            self,
            "Remove ROI",
            f"Are you sure you want to remove ROI #{roiIndex}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self.viewModel.removeRoi(self.viewModel.imageIndex, roiIndex)

    def renameRoi(self, roiIndex):
        """Rename an ROI"""
        newName, ok = QInputDialog.getText(
            self,
            "Rename ROI",
            f"Enter new name for ROI #{roiIndex}:",
            QLineEdit.EchoMode.Normal,
            f"ROI {roiIndex}",
        )

        if ok and newName:
            rois = self.viewModel.getROIs(self.viewModel.imageIndex)
            if roiIndex < len(rois):
                roi = rois[roiIndex]
                self.viewModel.updateRoi(roi.id, name=newName)

    def changeRoiColor(self, roiIndex):
        """Change the color of an ROI"""
        rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        if roiIndex >= len(rois):
            return

        roi = rois[roiIndex]

        # Show color dialog
        initialColor = (
            QColor(*roi.color[:3]) if hasattr(roi, "color") else QColor(255, 0, 0)
        )
        color = QColorDialog.getColor(
            initialColor, self, f"Select color for ROI #{roiIndex}"
        )

        if color.isValid():
            self.viewModel.updateRoi(roi.id, color=color)

    def onRoiAdded(self, roiId):
        """Handle ROI added signal from ViewModel"""
        self.updateROITable()
        self.statusLabel.setText(f"ROI {roiId} added")

    def onRoiRemoved(self, roiId):
        """Handle ROI removed signal from ViewModel"""
        self.updateROITable()
        if self.selectedRoiIndex is not None:
            self.selectedRoiIndex = None
            self.propertyEditor.setRoi(None, None)
        self.statusLabel.setText(f"ROI {roiId} removed")

    def onRoiUpdated(self, roiId):
        """Handle ROI updated signal from ViewModel"""
        self.updateROITable()
        self.statusLabel.setText(f"ROI {roiId} updated")

    def viewRoiStatistics(self):
        """View statistics for the selected ROI"""
        if self.selectedRoiIndex is None:
            QMessageBox.warning(self, "No ROI Selected", "Please select an ROI first.")
            return

        # Get all ROIs for the current image
        rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        if not rois or self.selectedRoiIndex >= len(rois):
            return

        # Get the selected ROI
        roi = rois[self.selectedRoiIndex]

        # Calculate statistics through ViewModel
        stats = self.viewModel.calculateRoiStatistics(roi.id)
        if not stats:
            QMessageBox.warning(
                self, "Statistics Error", "Could not calculate statistics for this ROI."
            )
            return

        # Show statistics dialog
        self.showStatisticsDialog(roi, stats)

    def showStatisticsDialog(self, roi, stats):
        """Show a dialog with ROI statistics"""
        from PyQt6.QtWidgets import (
            QDialog,
            QTabWidget,
            QVBoxLayout,
            QTableWidget,
            QTableWidgetItem,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(
            f"Statistics for ROI: {getattr(roi, 'name', f'ROI {self.selectedRoiIndex}')}"
        )
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)
        tabWidget = QTabWidget()

        # Summary tab
        summaryWidget = QWidget()
        summaryLayout = QVBoxLayout(summaryWidget)
        summaryTable = QTableWidget()
        summaryTable.setColumnCount(2)
        summaryTable.setHorizontalHeaderLabels(["Property", "Value"])

        # Add basic properties
        properties = [
            ("Number of pixels", stats.nPixels),
            ("Number of bands", stats.nBands),
            ("Area (pixels)", stats.nPixels),
            ("Mean values", "See Band Statistics Tab"),
            (
                "Created",
                (
                    roi.creationTime.strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(roi, "creationTime")
                    else "Unknown"
                ),
            ),
        ]

        summaryTable.setRowCount(len(properties))
        for i, (prop, value) in enumerate(properties):
            summaryTable.setItem(i, 0, QTableWidgetItem(prop))
            summaryTable.setItem(i, 1, QTableWidgetItem(str(value)))

        summaryLayout.addWidget(summaryTable)
        tabWidget.addTab(summaryWidget, "Summary")

        # Band statistics tab
        bandWidget = QWidget()
        bandLayout = QVBoxLayout(bandWidget)
        bandTable = QTableWidget()

        # Set up columns for band statistics
        statsColumns = [
            "Band",
            "Mean",
            "Median",
            "Std Dev",
            "Min",
            "Max",
            "25%",
            "75%",
        ]
        bandTable.setColumnCount(len(statsColumns))
        bandTable.setHorizontalHeaderLabels(statsColumns)

        # Add rows for each band
        bandTable.setRowCount(stats.nBands)
        for i in range(stats.nBands):
            bandStats = stats.getBandStats(i)
            bandTable.setItem(i, 0, QTableWidgetItem(str(i)))
            bandTable.setItem(i, 1, QTableWidgetItem(f"{bandStats['mean']:.4f}"))
            bandTable.setItem(i, 2, QTableWidgetItem(f"{bandStats['median']:.4f}"))
            bandTable.setItem(i, 3, QTableWidgetItem(f"{bandStats['stdDev']:.4f}"))
            bandTable.setItem(i, 4, QTableWidgetItem(f"{bandStats['min']:.4f}"))
            bandTable.setItem(i, 5, QTableWidgetItem(f"{bandStats['max']:.4f}"))
            bandTable.setItem(
                i, 6, QTableWidgetItem(f"{bandStats['percentile25']:.4f}")
            )
            bandTable.setItem(
                i, 7, QTableWidgetItem(f"{bandStats['percentile75']:.4f}")
            )

        bandLayout.addWidget(bandTable)
        tabWidget.addTab(bandWidget, "Band Statistics")

        # Add histogram tab if matplotlib is available
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

            histWidget = QWidget()
            histLayout = QVBoxLayout(histWidget)

            # Create figure and canvas
            fig, ax = plt.subplots(figsize=(8, 6))
            canvas = FigureCanvasQTAgg(fig)

            # Plot histogram for the first band
            binCenters, histValues = stats.histogram(0)
            ax.bar(
                binCenters,
                histValues,
                width=((binCenters[1] - binCenters[0]) if len(binCenters) > 1 else 0.1),
            )
            ax.set_title(f"Histogram for Band 0")
            ax.set_xlabel("Value")
            ax.set_ylabel("Frequency")

            histLayout.addWidget(canvas)
            tabWidget.addTab(histWidget, "Histogram")
        except ImportError:
            pass  # Skip histogram tab if matplotlib is not available

        layout.addWidget(tabWidget)
        dialog.setLayout(layout)
        dialog.exec()
