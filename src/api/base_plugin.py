from typing import Protocol, runtime_checkable, Callable


@runtime_checkable
class VPlugin(Protocol):
    """
    A protocol defining the interface for Varda plugins.
    Plugins should implement this interface to be recognized by the Varda application.
    """
    name: str
    description: str
    run: Callable[[], None]