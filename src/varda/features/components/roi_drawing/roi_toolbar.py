from PyQt6.QtWidgets import QWidget, QToolBar, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

class ROIMode:
    """Enum to define different ROI drawing modes"""

    FREEHAND = 0
    RECTANGLE = 1
    ELLIPSE = 2
    POLYGON = 3  # Click-by-click polygon

class ROIToolbarWidget(QWidget):
    def __init__(self, status_label, setDrawingMode, showAllROIs, hideAllROIs, parent=None):
        super().__init__(parent)
        self.status_label = status_label
        self.setDrawingMode = setDrawingMode
        self.showAllROIs = showAllROIs
        self.hideAllROIs = hideAllROIs

        self.toolbar = QToolBar("ROI Tools", self)

        # Drawing mode actions
        self.action_freehand = QAction("Freehand", self.toolbar)
        self.action_freehand.setCheckable(True)
        self.action_freehand.setChecked(True)
        self.action_freehand.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.FREEHAND)
        )

        self.action_rectangle = QAction("Rectangle", self.toolbar)
        self.action_rectangle.setCheckable(True)
        self.action_rectangle.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.RECTANGLE)
        )

        self.action_ellipse = QAction("Ellipse", self.toolbar)
        self.action_ellipse.setCheckable(True)
        self.action_ellipse.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.ELLIPSE)
        )

        self.action_polygon = QAction("Polygon", self.toolbar)
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
        self.toolbar.addAction(self.action_freehand)
        self.toolbar.addAction(self.action_rectangle)
        self.toolbar.addAction(self.action_ellipse)
        self.toolbar.addAction(self.action_polygon)
        self.toolbar.addSeparator()

        # Show/hide all ROIs
        self.action_show_all = QAction("Show All ROIs", self.toolbar)
        self.action_show_all.triggered.connect(self.showAllROIs)
        self.toolbar.addAction(self.action_show_all)

        self.action_hide_all = QAction("Hide All ROIs!!", self.toolbar)
        self.action_hide_all.triggered.connect(self.hideAllROIs)
        self.toolbar.addAction(self.action_hide_all)

        # Add status label
        self.toolbar.addWidget(self.status_label)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)