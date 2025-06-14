from typing import runtime_checkable, Protocol


@runtime_checkable
class VWidget(Protocol):
    """
    A protocol defining the interface for Varda widgets.
    Widgets should implement this interface to be recognized by the Varda application.
    """
    name: str
    description: str
    icon: str