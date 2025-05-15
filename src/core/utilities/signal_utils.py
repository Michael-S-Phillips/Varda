# src/core/utilities/signal_utils.py

import functools
import logging

logger = logging.getLogger(__name__)

def guard_signals(method):
    """Decorator to prevent recursive signal handling.
    
    This decorator automatically handles preventing recursive signal updates
    by setting a '_handling_change' flag on the object instance. Use it
    on methods that update UI elements in response to signals.
    
    Example:
        @guard_signals
        def _handleDataChanged(self, index, changeType):
            # Update UI elements...
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        # Check if we're already handling a change
        if getattr(self, '_handling_change', False):
            logger.debug(f"Prevented recursive call to {method.__name__}")
            return None
            
        # Set the flag before handling
        setattr(self, '_handling_change', True)
        try:
            # Call the original method
            result = method(self, *args, **kwargs)
            return result
        finally:
            # Always reset the flag, even if an exception occurs
            setattr(self, '_handling_change', False)
            
    return wrapper

class SignalBlocker:
    """Context manager to temporarily block signal handling.
    
    Use this with a 'with' statement to prevent recursive signals
    during a block of code where multiple properties might be updated.
    
    Example:
        with SignalBlocker(self):
            self.setValue1(10)
            self.setValue2(20)
            self.setValue3(30)
    """
    
    def __init__(self, instance):
        """Initialize with the instance whose signals we want to block.
        
        Args:
            instance: The object instance where '_handling_change' will be set
        """
        self.instance = instance
        self.previous_value = False
        
    def __enter__(self):
        """Save previous state and set blocking flag."""
        self.previous_value = getattr(self.instance, '_handling_change', False)
        setattr(self.instance, '_handling_change', True)
        return self.instance
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore previous state."""
        setattr(self.instance, '_handling_change', self.previous_value)
        # Don't suppress exceptions
        return False