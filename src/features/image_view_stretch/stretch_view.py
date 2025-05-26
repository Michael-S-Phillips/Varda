# src/features/image_view_stretch/stretch_view.py

"""
This module contains the ImageBasicStretchEditor class,
which is a custom widget that allows the user to edit the stretch.
"""

# standard library

# third party imports
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QHBoxLayout,
    QDoubleSpinBox,
    QWidget,
)
from PyQt6.QtCore import Qt

# local imports
from .stretch_viewmodel import StretchViewModel
from ..shared.selection_controls import StretchSelector
from core.utilities.signal_utils import SignalBlocker, guard_signals
from features.shared.base_view import BaseView


class StretchView(BaseView):
    """A custom widget that allows the user to view and edit stretch configurations.

    I'm going to skip having detailed documentation here because this will probably be
    replaced with a histogram tool very soon.
    """

    minRInput: QDoubleSpinBox
    maxRInput: QDoubleSpinBox
    minGInput: QDoubleSpinBox
    maxGInput: QDoubleSpinBox
    minBInput: QDoubleSpinBox
    maxBInput: QDoubleSpinBox
    stretchSelector: StretchSelector

    def __init__(self, viewModel: StretchViewModel, parent):
        super().__init__(viewModel, parent)
        self.setWindowTitle("Stretch Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self.initUI()
        self.connectSignals()
        self.show()

    def initUI(self):
        layout = QVBoxLayout(self)

        rLayout, self.minRInput, self.maxRInput = self.setupStretchLayout("Red", 0, 1)
        gLayout, self.minBInput, self.maxBInput = self.setupStretchLayout("Green", 0, 1)
        bLayout, self.minGInput, self.maxGInput = self.setupStretchLayout("Blue", 0, 1)

        self.stretchSelector = StretchSelector(
            self.viewModel.proj, self.viewModel.index
        )
        layout.addWidget(self.stretchSelector)
        layout.addLayout(rLayout)
        layout.addLayout(gLayout)
        layout.addLayout(bLayout)

        self.setLayout(layout)

    def setupStretchLayout(self, name, val1, val2):
        spinBox1 = QDoubleSpinBox()
        spinBox1.setValue(val1)
        spinBox2 = QDoubleSpinBox()
        spinBox2.setValue(val2)
        label = QLabel(name)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(spinBox1)
        layout.addWidget(spinBox2)
        return layout, spinBox1, spinBox2

    def connectSignals(self):
        self.viewModel.sigStretchChanged.connect(self.onStretchChanged)
        self.stretchSelector.currentIndexChanged.connect(self.viewModel.selectStretch)
        self.minRInput.valueChanged.connect(self.updateStretch)
        self.maxRInput.valueChanged.connect(self.updateStretch)
        self.minGInput.valueChanged.connect(self.updateStretch)
        self.maxGInput.valueChanged.connect(self.updateStretch)
        self.minBInput.valueChanged.connect(self.updateStretch)
        self.maxBInput.valueChanged.connect(self.updateStretch)

    def updateStretch(self):
        """Update the stretch configuration in the ViewModel."""
        self.viewModel.updateStretch(
            self.minRInput.value(),
            self.maxRInput.value(),
            self.minGInput.value(),
            self.maxGInput.value(),
            self.minBInput.value(),
            self.maxBInput.value(),
        )

    @guard_signals
    def onStretchChanged(self):
        """Handle stretch changes from the ViewModel.

        This method updates the UI with new stretch values.
        The @guard_signals decorator prevents recursive updates when
        the UI change triggers valueChanged signals.
        """
        stretch = self.viewModel.getSelectedStretch()
        self.minRInput.setValue(stretch.minR)
        self.maxRInput.setValue(stretch.maxR)
        self.minGInput.setValue(stretch.minG)
        self.maxGInput.setValue(stretch.maxG)
        self.minBInput.setValue(stretch.minB)
        self.maxBInput.setValue(stretch.maxB)

    def updateMultipleValues(self, values):
        """Example method showing how to use SignalBlocker for multiple UI updates."""
        # This prevents UI updates from triggering more signal handling
        with SignalBlocker(self):
            self.minRInput.setValue(values[0])
            self.maxRInput.setValue(values[1])
            self.minGInput.setValue(values[2])
            self.maxGInput.setValue(values[3])
            self.minBInput.setValue(values[4])
            self.maxBInput.setValue(values[5])

        # Now that all values are updated, we can refresh the UI once
        # This would typically call some method to update the display
