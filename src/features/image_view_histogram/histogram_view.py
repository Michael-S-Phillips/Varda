# src/features/image_view_histogram/histogram_view.py

# standard library
import logging
# third-party imports
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QTabWidget, QMessageBox, QGroupBox, QComboBox, QPushButton, QLabel
from PyQt6.QtGui import QColor
from pyqtgraph import HistogramLUTItem

# local imports
from features.shared.selection_controls import StretchSelector, BandSelector
from .histogram_viewmodel import HistogramViewModel
from core.stretch.stretch_manager import StretchPresets
from features.shared.base_view import BaseView
from core.utilities.signal_utils import guard_signals, SignalBlocker

logger = logging.getLogger(__name__)

class DualHistogram(QWidget):
    def __init__(self, parent=None, image=None, color=(255, 255, 255)):
        super().__init__(parent)
        self.color = color
        self.image = image
        self._initUI()
        self._connectSignals()

    def _initUI(self):
        # First (main) histogram
        self.histogram = pg.HistogramLUTWidget(
            self, image=self.image, orientation="horizontal"
        )

        self.histogram.item.regions[0].setBrush(QColor(*(*self.color, 25)))
        self.histogram.item.regions[0].setHoverBrush(QColor(*(*self.color, 50)))
        self.histogram.item.gradient.hide()
        self.histogram.item.fillHistogram(True, level=0.0, color=(*self.color, 50))
        self.histogram.item.disableAutoHistogramRange()

        # Second (zoomed) histogram
        self.histogramZoomed = pg.HistogramLUTWidget(
            self, image=self.image, orientation="horizontal"
        )
        zoomedColor = (self.color[0], self.color[1], self.color[2], 50)
        self.histogramZoomed.item.fillHistogram(True, level=0.0, color=zoomedColor)
        self.histogramZoomed.item.gradient.hide()
        self.histogramZoomed.item.regions[0].hide()
        self.histogramZoomed.item.vb.setMouseEnabled(x=False, y=False)

        # Layout: Stack two histograms vertically
        layout = QVBoxLayout()
        layout.addWidget(self.histogram)
        layout.addWidget(self.histogramZoomed)
        self.setLayout(layout)

    def _connectSignals(self):
        self.histogram.item.sigLevelsChanged.connect(self._handleLevelsChanged)

    def _handleLevelsChanged(self):
        mn, mx = self.histogram.item.getLevels()
        self.histogramZoomed.item.setHistogramRange(mn, mx)

class HistogramView(BaseView):
    """A basic view for editing band configurations of an image with selectable RGB histograms."""

    def __init__(self, viewModel: HistogramViewModel = None, parent=None):
        super().__init__(viewModel, parent)
        self.setWindowTitle("Histogram")

        # To link the histograms to the image, we use an ImageItem.
        # This is just to leverage the existing functionality of the HistogramLUTWidget.
        self.imageItemR = pg.ImageItem()
        self.imageItemG = pg.ImageItem()
        self.imageItemB = pg.ImageItem()
        self._updateImageItems()

        self._initUI()
        self.connectViewModelSignals()
        
    def _initUI(self):
        self.tabWidget = QTabWidget()

        self.histogramR = DualHistogram(self, self.imageItemR, color=(255, 0, 0))
        self.histogramG = DualHistogram(self, self.imageItemG, color=(0, 255, 0))
        self.histogramB = DualHistogram(self, self.imageItemB, color=(0, 0, 255))

        self.tabWidget.addTab(self.histogramR, "Red")
        self.tabWidget.addTab(self.histogramG, "Green")
        self.tabWidget.addTab(self.histogramB, "Blue")

        # Add stretch preset options
        self.presetsGroup = QGroupBox("Preset Stretches")
        self.presetsLayout = QVBoxLayout()
        
        # Add a dropdown for selecting presets
        self.presetCombo = QComboBox()
        for _, preset_name in StretchPresets.get_preset_names():
            self.presetCombo.addItem(preset_name)
        
        self.applyPresetButton = QPushButton("Apply Selected Preset")
        self.applyPresetButton.clicked.connect(self._onApplyPresetClicked)
        
        self.presetsLayout.addWidget(QLabel("Select a preset stretch:"))
        self.presetsLayout.addWidget(self.presetCombo)
        self.presetsLayout.addWidget(self.applyPresetButton)
        
        self.presetsGroup.setLayout(self.presetsLayout)
        
        selectorLayout = QVBoxLayout()
        selectorLayout.addWidget(self.presetsGroup)

        layout = QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.addWidget(self.tabWidget)
        self.setLayout(layout)

    def connectViewModelSignals(self):
        """Connect to signals from the ViewModel."""
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)

        self.histogramR.histogram.item.sigLevelsChanged.connect(self._onHistogramLevelsChanged)
        self.histogramG.histogram.item.sigLevelsChanged.connect(self._onHistogramLevelsChanged)
        self.histogramB.histogram.item.sigLevelsChanged.connect(self._onHistogramLevelsChanged)

    def _updateImageItems(self):
        """Update the image items with current raster data."""
        data = self.viewModel.getRasterFromBand()
        self.imageItemR.setImage(data[:, :, 0], autoLevels=False)
        self.imageItemG.setImage(data[:, :, 1], autoLevels=False)
        self.imageItemB.setImage(data[:, :, 2], autoLevels=False)

    def _onApplyPresetClicked(self):
        """Apply the selected preset stretch."""
        try:
            # Get the selected preset
            preset_index = self.presetCombo.currentIndex()
            preset_id = StretchPresets.get_preset_names()[preset_index][0]
            
            # Get the image data
            image = self.viewModel.proj.getImage(self.viewModel.index)
            image_data = image.raster
            
            # Create a stretch from the preset
            stretch = StretchPresets.create_stretch_from_preset(preset_id, image_data)
            
            # Add the stretch to the project
            self.viewModel.proj.addStretch(self.viewModel.index, stretch)
            
            # Select the new stretch
            self.viewModel.selectStretch(len(image.stretch) - 1)
            
        except Exception as e:
            logger.error(f"Error applying preset stretch: {e}")
            # Show an error message
            QMessageBox.warning(
                self, 
                "Stretch Error",
                f"Error applying stretch preset: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    @guard_signals
    def _onHistogramLevelsChanged(self):
        """Handle changes to histogram levels.
        
        Updates the stretch parameters in the ViewModel based on 
        the current histogram levels. Protected against recursive
        updates by the guard_signals decorator.
        """
        minR, maxR = self.histogramR.histogram.item.getLevels()
        minG, maxG = self.histogramG.histogram.item.getLevels()
        minB, maxB = self.histogramB.histogram.item.getLevels()

        self.viewModel.updateStretch(minR=minR, maxR=maxR, minG=minG, maxG=maxG, minB=minB, maxB=maxB)

    def _onBandChanged(self):
        """Handle band changes by updating image items."""
        self._updateImageItems()

    @guard_signals
    def _onStretchChanged(self, minR, maxR, minG, maxG, minB, maxB):
        """Handle stretch changes by updating histogram levels.
        
        Protected against recursive updates by the guard_signals decorator.
        """
        # Update all histogram levels at once using SignalBlocker
        with SignalBlocker(self):
            self.histogramR.histogram.item.setLevels(minR, maxR)
            self.histogramG.histogram.item.setLevels(minG, maxG)
            self.histogramB.histogram.item.setLevels(minB, maxB)
    
    def updateUI(self):
        """Update the UI based on the current ViewModel state."""
        # Get current stretch values
        stretch = self.viewModel.getSelectedStretch()
        
        # Use SignalBlocker to prevent recursive updates
        with SignalBlocker(self):
            self.histogramR.histogram.item.setLevels(stretch.minR, stretch.maxR)
            self.histogramG.histogram.item.setLevels(stretch.minG, stretch.maxG)
            self.histogramB.histogram.item.setLevels(stretch.minB, stretch.maxB)
            
        # Update image data
        self._updateImageItems()