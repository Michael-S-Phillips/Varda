# src/features/image_view_stretch/custom_stretch_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QComboBox, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt

class CustomStretchDialog(QDialog):
    """Dialog for creating a custom stretch with user-defined parameters."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Stretch")
        self.resize(400, 300)
        
        # Initialize layout
        self.layout = QVBoxLayout(self)
        
        # Create type selection
        self.typeLabel = QLabel("Stretch Type:")
        self.typeCombo = QComboBox()
        self.typeCombo.addItems([
            "Percentile",
            "Gaussian",
            "Logarithmic",
            "Decorrelation",
            "Adaptive Equalization"
        ])
        self.typeCombo.currentIndexChanged.connect(self._onTypeChanged)
        
        typeLayout = QHBoxLayout()
        typeLayout.addWidget(self.typeLabel)
        typeLayout.addWidget(self.typeCombo)
        self.layout.addLayout(typeLayout)
        
        # Create parameter form
        self.formLayout = QFormLayout()
        self.layout.addLayout(self.formLayout)
        
        # Create button box
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)
        
        # Initialize for the first type
        self._onTypeChanged(0)
    
    def _onTypeChanged(self, index):
        """Update form for the selected stretch type."""
        # Clear existing form widgets
        while self.formLayout.rowCount() > 0:
            self.formLayout.removeRow(0)
        
        stretch_type = self.typeCombo.currentText()
        
        if stretch_type == "Percentile":
            # Create widgets for percentile stretch
            self.lowPercentile = QDoubleSpinBox()
            self.lowPercentile.setRange(0.0, 49.0)
            self.lowPercentile.setValue(2.0)
            self.lowPercentile.setDecimals(1)
            
            self.highPercentile = QDoubleSpinBox()
            self.highPercentile.setRange(51.0, 100.0)
            self.highPercentile.setValue(98.0)
            self.highPercentile.setDecimals(1)
            
            self.formLayout.addRow("Low Percentile:", self.lowPercentile)
            self.formLayout.addRow("High Percentile:", self.highPercentile)
            
        elif stretch_type == "Gaussian":
            # Create widgets for Gaussian stretch
            self.sigmaFactor = QDoubleSpinBox()
            self.sigmaFactor.setRange(0.5, 5.0)
            self.sigmaFactor.setValue(2.0)
            self.sigmaFactor.setDecimals(1)
            
            self.formLayout.addRow("Sigma Factor:", self.sigmaFactor)
            
        elif stretch_type == "Logarithmic":
            # Create widgets for logarithmic stretch
            self.gain = QDoubleSpinBox()
            self.gain.setRange(0.1, 10.0)
            self.gain.setValue(1.0)
            self.gain.setDecimals(1)
            
            self.formLayout.addRow("Gain:", self.gain)
            
        elif stretch_type == "Decorrelation":
            # Create widgets for decorrelation stretch
            self.scalingFactor = QDoubleSpinBox()
            self.scalingFactor.setRange(1.0, 5.0)
            self.scalingFactor.setValue(2.5)
            self.scalingFactor.setDecimals(1)
            
            self.formLayout.addRow("Scaling Factor:", self.scalingFactor)
            
        elif stretch_type == "Adaptive Equalization":
            # Create widgets for adaptive equalization
            self.clipLimit = QDoubleSpinBox()
            self.clipLimit.setRange(0.001, 0.05)
            self.clipLimit.setValue(0.01)
            self.clipLimit.setDecimals(3)
            
            self.tileSize = QSpinBox()
            self.tileSize.setRange(4, 16)
            self.tileSize.setValue(8)
            
            self.formLayout.addRow("Clip Limit:", self.clipLimit)
            self.formLayout.addRow("Tile Size:", self.tileSize)
    
    def getParameters(self):
        """Get the selected stretch type and parameters."""
        stretch_type = self.typeCombo.currentText()
        params = {}
        
        if stretch_type == "Percentile":
            params["algorithm_id"] = "percentile"
            params["low_percentile"] = self.lowPercentile.value()
            params["high_percentile"] = self.highPercentile.value()
            
        elif stretch_type == "Gaussian":
            params["algorithm_id"] = "gaussian"
            params["sigma_factor"] = self.sigmaFactor.value()
            
        elif stretch_type == "Logarithmic":
            params["algorithm_id"] = "logarithmic"
            params["gain"] = self.gain.value()
            
        elif stretch_type == "Decorrelation":
            params["algorithm_id"] = "decorrelation"
            params["scaling_factor"] = self.scalingFactor.value()
            
        elif stretch_type == "Adaptive Equalization":
            params["algorithm_id"] = "adaptive_eq"
            params["clip_limit"] = self.clipLimit.value()
            params["tile_size"] = self.tileSize.value()
        
        return params