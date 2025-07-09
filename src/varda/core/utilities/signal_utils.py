# varda/core/utilities/signal_utils.py

import functools
import logging

logger = logging.getLogger(__name__)


def guard_signals(force_critical=False):
    """Decorator to prevent recursive signal handling with option to force critical updates.

    Args:
        force_critical: If True, allows certain critical signals to propagate despite recursion
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Check if we're already handling a change
            if getattr(self, "_handling_change", False) and not force_critical:
                logger.debug(f"Prevented recursive call to {method.__name__}")
                return None
            logger.debug(f"Call is not recursive! proceeding with {method.__name__}")
            # Set the flag before handling
            prev_state = getattr(self, "_handling_change", False)
            setattr(self, "_handling_change", True)
            try:
                # Call the original method
                result = method(self, *args, **kwargs)
                return result
            finally:
                # Always reset the flag, even if an exception occurs
                setattr(self, "_handling_change", prev_state)

        return wrapper

    # Handle both @guard_signals and @guard_signals(force_critical=True) syntax
    if callable(force_critical):
        # Used as @guard_signals without parameters
        method = force_critical
        force_critical = False
        return decorator(method)
    else:
        # Used as @guard_signals(force_critical=...)
        return decorator


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
        self.previous_value = getattr(self.instance, "_handling_change", False)
        setattr(self.instance, "_handling_change", True)
        return self.instance

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore previous state."""
        setattr(self.instance, "_handling_change", self.previous_value)
        # Don't suppress exceptions
        return False
