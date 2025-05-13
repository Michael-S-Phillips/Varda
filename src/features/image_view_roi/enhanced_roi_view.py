import logging
from typing import List, Dict, Optional, Any, Tuple, NamedTuple
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QToolButton, QMenu, QAction, QHeaderView, QLabel,
    QComboBox, QCheckBox, QColorDialog, QInputDialog, QMessageBox,
    QTabWidget, QSplitter, QLineEdit, QGroupBox, QFormLayout,
    QSlider, QTextEdit, QDialog, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap

from core.data import ProjectContext
from core.entities.freehandROI import FreehandROI
from .roi_viewmodel import ROIViewModel


logger = logging.getLogger(__name__)


class ROITableColumn(NamedTuple):
    """Represents a column in the ROI table with display settings"""
    name: str
    visible: bool = True
    width: int = 100
    editable: bool = True


class ROITableWidget(QTableWidget):
    """Enhanced table widget for displaying and managing ROIs"""
    
    roiSelectionChanged = pyqtSignal(int)  # Emits ROI index when selection changes
    roiDoubleClicked = pyqtSignal(int)  # Emits ROI index when double-clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | 
                            QTableWidget.EditTrigger.SelectedClicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.itemSelectionChanged.connect(self.onSelectionChanged)
        self.cellDoubleClicked.connect(self.onCellDoubleClicked)
        
        # Set up right-click menu
        self.contextMenu = QMenu(self)
        self.setup_context_menu()
        
    def setup_context_menu(self):
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
            self.parent().toggle_roi_visibility(row)
    
    def onPlotSpectrum(self):
        """Plot the spectrum of the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().plot_roi_spectrum(row)
    
    def onRemoveROI(self):
        """Remove the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().remove_roi(row)
    
    def onRenameROI(self):
        """Rename the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().rename_roi(row)
    
    def onChangeColor(self):
        """Change the color of the selected ROI"""
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self.parent().change_roi_color(row)


class ROIPropertyEditor(QWidget):
    """Widget for editing ROI properties"""
    
    propertyChanged = pyqtSignal(int, str, object)  # ROI index, property name, value
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_roi_index = None
        
        layout = QVBoxLayout()
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(lambda text: self.onPropertyChanged("name", text))
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_button = QPushButton()
        self.color_button.setFixedSize(24, 24)
        self.color_button.clicked.connect(self.onChangeColor)
        color_layout.addWidget(self.color_button)
        layout.addLayout(color_layout)
        
        # Opacity (simulated with alpha value)
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.valueChanged.connect(lambda value: self.onPropertyChanged("opacity", value / 100.0))
        opacity_layout.addWidget(self.opacity_slider)
        layout.addLayout(opacity_layout)
        
        # Visibility (simulated)
        visibility_layout = QHBoxLayout()
        self.visible_checkbox = QCheckBox("Visible")
        self.visible_checkbox.setChecked(True)
        self.visible_checkbox.toggled.connect(lambda checked: self.onPropertyChanged("visible", checked))
        visibility_layout.addWidget(self.visible_checkbox)
        layout.addLayout(visibility_layout)
        
        # Information
        info_group = QGroupBox("Information")
        info_layout = QFormLayout()
        self.points_label = QLabel("0")
        info_layout.addRow("Points:", self.points_label)
        self.image_index_label = QLabel("0")
        info_layout.addRow("Image Index:", self.image_index_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout()
        self.mean_label = QLabel("N/A")
        stats_layout.addRow("Mean Value:", self.mean_label)
        self.std_label = QLabel("N/A")
        stats_layout.addRow("Std Deviation:", self.std_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Add stretch at the bottom
        layout.addStretch()
        
        self.setLayout(layout)
        self.setEnabled(False)  # Disable until an ROI is selected
    
    def set_roi(self, roi: FreehandROI, index: int):
        """Set the ROI to edit"""
        if roi is None:
            self.current_roi_index = None
            self.setEnabled(False)
            return
            
        self.current_roi_index = index
        self.setEnabled(True)
        
        # Block signals during updates
        self.blockSignals(True)
        
        self.name_edit.setText(f"ROI {index}")
        self.update_color_button(roi.color)
        self.opacity_slider.setValue(50)  # Default 50% opacity
        self.visible_checkbox.setChecked(True)  # Default visible
        
        # Update information
        if roi.points is not None:
            self.points_label.setText(str(len(roi.points[0])))  # Points is a list of two lists [x_values, y_values]
        else:
            self.points_label.setText("0")
            
        self.image_index_label.setText(str(roi.imageIndex))
        
        # Update statistics if available
        if roi.meanSpectrum is not None:
            mean_value = float(roi.meanSpectrum.mean())
            self.mean_label.setText(f"{mean_value:.4f}")
            
            # Std is not available in the current ROI class, so we'll set a placeholder
            self.std_label.setText("N/A")
        else:
            self.mean_label.setText("N/A")
            self.std_label.setText("N/A")
        
        self.blockSignals(False)
    
    def update_color_button(self, color: str):
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
        self.color_button.setStyleSheet(style)
    
    def onChangeColor(self):
        """Open a color dialog to change the ROI color"""
        if self.current_roi_index is None:
            return
            
        initial_color = self.color_button.palette().button().color()
        color = QColorDialog.getColor(
            initial=initial_color, 
            parent=self, 
            title="Select ROI Color"
        )
        
        if color.isValid():
            self.update_color_button(color.name())
            self.onPropertyChanged("color", color.name())
    
    def onPropertyChanged(self, property_name: str, value: Any):
        """Emit a signal when a property is changed"""
        if self.current_roi_index is not None and not self.signalsBlocked():
            self.propertyChanged.emit(self.current_roi_index, property_name, value)


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
            item.setCheckState(Qt.CheckState.Checked if column.visible else Qt.CheckState.Unchecked)
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
            result.append(ROITableColumn(
                name=column.name,
                visible=item.checkState() == Qt.CheckState.Checked,
                width=column.width,
                editable=column.editable
            ))
        return result


class EnhancedROIView(QWidget):
    """Enhanced view for ROI management"""
    
    roiSelectionChanged = pyqtSignal(int)  # Emits ROI index when selection changes
    
    def __init__(self, viewModel: ROIViewModel, parent=None):
        super().__init__(parent)
        self.viewModel = viewModel
        self.viewModel.setView(self)  # Set reference to this view in the viewModel
        self.selectedRoiIndex = None
        self.blinkState = False
        self.blinkTimer = None
        
        # Define default columns
        self.columns = [
            ROITableColumn("Index", True, 60, False),
            ROITableColumn("Color", True, 60, False),
            ROITableColumn("Points", True, 60, False),
            ROITableColumn("Image Index", True, 80, False),
            ROITableColumn("Mean Spectrum", True, 120, False),
            ROITableColumn("Actions", True, 120, False)
        ]
        
        self.initUI()
        self.connectSignals()
        self.updateROITable()
    
    def initUI(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout()
        
        # Header with buttons
        header_layout = QHBoxLayout()
        
        self.draw_roi_button = QPushButton("Draw ROI", self)
        self.draw_roi_button.setToolTip("Start drawing a new ROI")
        header_layout.addWidget(self.draw_roi_button)
        
        self.show_all_button = QPushButton("Show All", self)
        self.show_all_button.setToolTip("Show all ROIs")
        header_layout.addWidget(self.show_all_button)
        
        self.hide_all_button = QPushButton("Hide All", self)
        self.hide_all_button.setToolTip("Hide all ROIs")
        header_layout.addWidget(self.hide_all_button)
        
        self.blink_button = QPushButton("Blink", self)
        self.blink_button.setCheckable(True)
        self.blink_button.setToolTip("Toggle blinking of ROIs")
        header_layout.addWidget(self.blink_button)
        
        header_layout.addStretch()
        
        # Column management
        self.manage_columns_button = QPushButton("Manage Columns", self)
        self.manage_columns_button.setToolTip("Manage which columns are displayed")
        header_layout.addWidget(self.manage_columns_button)
        
        main_layout.addLayout(header_layout)
        
        # Splitter for table and properties
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ROI Table
        self.roi_table = ROITableWidget(self)
        self.setupROITable()
        splitter.addWidget(self.roi_table)
        
        # Property editor
        self.property_editor = ROIPropertyEditor(self)
        splitter.addWidget(self.property_editor)
        
        # Set initial sizes
        splitter.setSizes([int(self.width() * 0.7), int(self.width() * 0.3)])
        
        main_layout.addWidget(splitter, 1)  # Give the splitter stretch
        
        self.setLayout(main_layout)
    
    def setupROITable(self):
        """Set up the ROI table with columns"""
        visible_columns = [col for col in self.columns if col.visible]
        self.roi_table.setColumnCount(len(visible_columns))
        header_labels = [col.name for col in visible_columns]
        self.roi_table.setHorizontalHeaderLabels(header_labels)
        
        # Set column widths
        for i, col in enumerate(visible_columns):
            self.roi_table.setColumnWidth(i, col.width)
            
        # Set table properties
        self.roi_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.roi_table.horizontalHeader().setStretchLastSection(True)
    
    def connectSignals(self):
        """Connect UI signals"""
        self.draw_roi_button.clicked.connect(self.startDrawingROI)
        self.show_all_button.clicked.connect(self.showAllROIs)
        self.hide_all_button.clicked.connect(self.hideAllROIs)
        self.blink_button.clicked.connect(self.toggleBlinkROIs)
        self.manage_columns_button.clicked.connect(self.showManageColumnsDialog)
        
        self.roi_table.roiSelectionChanged.connect(self.onRoiSelectionChanged)
        self.roi_table.roiDoubleClicked.connect(self.onRoiDoubleClicked)
        
        self.property_editor.propertyChanged.connect(self.onRoiPropertyChanged)
    
    def updateROITable(self, rois=None):
        """Update the ROI table with current data"""
        if rois is None:
            rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        
        # Clear the table
        self.roi_table.setRowCount(0)
        
        # Add the rows
        for i, roi in enumerate(rois):
            self.roi_table.insertRow(i)
            
            visible_columns = [col for col in self.columns if col.visible]
            for j, col in enumerate(visible_columns):
                item = self.createTableItem(roi, col.name, i)
                if item:
                    if not col.editable:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.roi_table.setItem(i, j, item)
        
        # If a ROI was selected, try to reselect it
        if self.selectedRoiIndex is not None and self.selectedRoiIndex < len(rois):
            self.roi_table.selectRow(self.selectedRoiIndex)
    
    def createTableItem(self, roi, column_name, roi_index):
        """Create a table item for the given ROI and column"""
        item = QTableWidgetItem()
        
        # Set the value based on column type
        if column_name == "Index":
            item.setText(str(roi_index))
        elif column_name == "Color":
            item.setText("")
            item.setBackground(QBrush(QColor(roi.color)))
        elif column_name == "Points":
            if roi.points is not None:
                item.setText(str(len(roi.points[0])))
            else:
                item.setText("0")
        elif column_name == "Image Index":
            item.setText(str(roi.imageIndex))
        elif column_name == "Mean Spectrum":
            if roi.meanSpectrum is not None:
                item.setText("Available")
            else:
                item.setText("Not calculated")
        elif column_name == "Actions":
            # For actions column, we would typically create a widget with buttons
            # But QTableWidgetItem doesn't support widgets directly
            # For now, just add text indicating actions are available
            item.setText("Plot | Export")
        
        return item
    
    def startDrawingROI(self):
        """Start drawing a new ROI"""
        self.viewModel.startDrawingROI()
    
    def showAllROIs(self):
        """Show all ROIs (currently a placeholder)"""
        QMessageBox.information(self, "Show All ROIs", "This feature would show all ROIs.")
        # In a complete implementation, this would update ROI visibility
    
    def hideAllROIs(self):
        """Hide all ROIs (currently a placeholder)"""
        QMessageBox.information(self, "Hide All ROIs", "This feature would hide all ROIs.")
        # In a complete implementation, this would update ROI visibility
    
    def toggleBlinkROIs(self, checked):
        """Toggle ROI blinking"""
        if checked:
            # Start blinking timer
            if self.blinkTimer is None:
                self.blinkTimer = QTimer(self)
                self.blinkTimer.timeout.connect(self.blinkROIs)
            self.blinkTimer.start(500)  # Blink every 500ms
        else:
            # Stop blinking
            if self.blinkTimer is not None:
                self.blinkTimer.stop()
            # Show all ROIs again
            self.showAllROIs()
    
    def blinkROIs(self):
        """Blink ROIs by toggling visibility (placeholder implementation)"""
        self.blinkState = not self.blinkState
        logger.debug(f"Blinking ROIs: {'visible' if self.blinkState else 'hidden'}")
        # In a complete implementation, this would toggle ROI visibility in the view
    
    def showManageColumnsDialog(self):
        """Show the manage columns dialog"""
        dialog = ROIColumnManager(self.columns, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.columns = dialog.getVisibleColumns()
            self.setupROITable()
            self.updateROITable()
    
    def onRoiSelectionChanged(self, roi_index):
        """Handle ROI selection change"""
        if roi_index >= 0 and roi_index < len(self.viewModel.getROIs(self.viewModel.imageIndex)):
            self.selectedRoiIndex = roi_index
            rois = self.viewModel.getROIs(self.viewModel.imageIndex)
            if roi_index < len(rois):
                roi = rois[roi_index]
                self.property_editor.set_roi(roi, roi_index)
                self.roiSelectionChanged.emit(roi_index)
    
    def onRoiDoubleClicked(self, roi_index):
        """Handle ROI double-click"""
        self.plot_roi_spectrum(roi_index)
    
    def onRoiPropertyChanged(self, roi_index, property_name, value):
        """Handle property change from property editor"""
        # In a complete implementation, this would update the ROI in the viewModel
        logger.debug(f"ROI property changed: ROI {roi_index}, {property_name} = {value}")
        
        if property_name == "color":
            # Update color in the table
            rois = self.viewModel.getROIs(self.viewModel.imageIndex)
            if roi_index < len(rois):
                col_idx = next((i for i, col in enumerate(self.columns) 
                               if col.name == "Color" and col.visible), -1)
                if col_idx >= 0:
                    item = self.roi_table.item(roi_index, col_idx)
                    if item:
                        item.setBackground(QBrush(QColor(value)))
    
    def toggle_roi_visibility(self, roi_index):
        """Toggle visibility of an ROI (placeholder implementation)"""
        logger.debug(f"Toggle visibility for ROI {roi_index}")
        # In a complete implementation, this would update ROI visibility
    
    def plot_roi_spectrum(self, roi_index):
        """Plot the spectrum of an ROI"""
        rois = self.viewModel.getROIs(self.viewModel.imageIndex)
        if roi_index < len(rois):
            roi = rois[roi_index]
            self.viewModel.plotMeanSpectrum(roi)
    
    def remove_roi(self, roi_index):
        """Remove an ROI"""
        confirm = QMessageBox.question(
            self, 
            "Remove ROI", 
            f"Are you sure you want to remove ROI #{roi_index}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.viewModel.removeROI(self.viewModel.imageIndex, roi_index)
            self.updateROITable()
            if self.selectedRoiIndex == roi_index:
                self.selectedRoiIndex = None
                self.property_editor.set_roi(None, None)
    
    def rename_roi(self, roi_index):
        """Rename an ROI (placeholder implementation)"""
        new_name, ok = QInputDialog.getText(
            self,
            "Rename ROI",
            f"Enter new name for ROI #{roi_index}:",
            QLineEdit.EchoMode.Normal,
            f"ROI {roi_index}"
        )
        
        if ok and new_name:
            logger.debug(f"Renaming ROI {roi_index} to '{new_name}'")
            # In a complete implementation, this would update the ROI name
    
    def change_roi_color(self, roi_index):
        """Change the color of an ROI"""
        color = QColorDialog.getColor(
            QColor(255, 0, 0),  # Default red
            self,
            f"Select color for ROI #{roi_index}"
        )
        
        if color.isValid():
            logger.debug(f"Changing color of ROI {roi_index} to {color.name()}")
            self.onRoiPropertyChanged(roi_index, "color", color.name())


def getROIView(proj, index, parent):
    """Sets up and returns an instance of EnhancedROIView."""
    viewModel = ROIViewModel(proj, index, parent)
    view = EnhancedROIView(viewModel, parent)
    return view