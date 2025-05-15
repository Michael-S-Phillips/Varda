# src/features/shared/base_view.py (new file)

from PyQt6.QtWidgets import QWidget
import logging

logger = logging.getLogger(__name__)

class BaseView(QWidget):
    """Base class for all feature views to reduce code duplication."""
    
    def __init__(self, viewModel, parent=None):
        super().__init__(parent)
        self.viewModel = viewModel
        self._handling_change = False  # Prevent infinite signal loops
        
    def _guard_against_recursion(self, func):
        """Decorator-like method to prevent recursive signal handling."""
        if self._handling_change:
            return
            
        self._handling_change = True
        try:
            return func()
        finally:
            self._handling_change = False
            
    def connectViewModelSignals(self):
        """Connect to ViewModel signals - override in subclasses."""
        pass
            
    def updateUI(self):
        """Update UI from ViewModel state - override in subclasses."""
        pass