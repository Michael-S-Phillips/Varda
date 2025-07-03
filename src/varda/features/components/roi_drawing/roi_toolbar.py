from PyQt6.QtWidgets import (
    QWidget,
    QToolBar,
    QVBoxLayout,
    QLabel,
    QMenu,
    QMenuBar,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from varda.core.entities import ROIMode


class ROIToolbarWidget(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        # self.status_label = status_label
        # self.setDrawingMode = setDrawingMode
        # self.showAllROIs = showAllROIs
        # self.hideAllROIs = hideAllROIs
        self.setWindowTitle("ROI Tools")

        # Drawing mode actions
        self.action_freehand = QAction("Freehand", self)
        self.action_freehand.setCheckable(True)
        self.action_freehand.setChecked(True)
        self.action_freehand.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.FREEHAND)
        )

        self.action_rectangle = QAction("Rectangle", self)
        self.action_rectangle.setCheckable(True)
        self.action_rectangle.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.RECTANGLE)
        )

        self.action_ellipse = QAction("Ellipse", self)
        self.action_ellipse.setCheckable(True)
        self.action_ellipse.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.ELLIPSE)
        )

        self.action_polygon = QAction("Polygon", self)
        self.action_polygon.setCheckable(True)
        self.action_polygon.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.POLYGON)
        )

        # Group actions for mutual exclusion
        self.draw_mode_actions = [
            self.action_freehand,
            self.action_rectangle,
            self.action_ellipse,
            self.action_polygon,
        ]

        # Add actions to toolbar
        testMenubar = QMenuBar(self)
        testMenubar.setNativeMenuBar(False)
        testMenubar.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        testMenu = QMenu(self)
        testMenu.setTitle("Test Menu")
        testMenu.addAction(self.action_freehand)
        testMenu.addAction(self.action_rectangle)
        testMenu.addAction(self.action_ellipse)
        testMenubar.addMenu(testMenu)
        self.addWidget(testMenubar)
        self.addWidget(QLabel("TESTLABEL", self))
        self.addAction(self.action_freehand)
        self.addAction(self.action_rectangle)
        self.addAction(self.action_ellipse)
        self.addAction(self.action_polygon)
        self.addSeparator()

        # Show/hide all ROIs
        self.action_show_all = QAction("Show All ROIs", self)
        # self.action_show_all.triggered.connect(self.showAllROIs)
        self.addAction(self.action_show_all)

        self.action_hide_all = QAction("Hide All ROIs!!", self)
        # self.action_hide_all.triggered.connect(self.hideAllROIs)
        self.addAction(self.action_hide_all)

        # Add status label
        # self.addWidget(self.status_label)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def setDrawingMode(self, mode):
        """Set the current ROI drawing mode"""
        self.drawingMode = mode

        # Update action checkboxes
        for action in self.draw_mode_actions:
            action.setChecked(False)
        self.draw_mode_actions[mode].setChecked(True)

        # Update status message
        mode_names = ["Freehand", "Rectangle", "Ellipse", "Polygon"]
        # self.status_label.setText(f"Drawing Mode: {mode_names[mode]}")
