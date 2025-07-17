"""
Protocol for image processing operations.
"""

from typing import Protocol, runtime_checkable, Dict, Any


@runtime_checkable
class ImageProcess(Protocol):
    """Base protocol for image processing operations"""

    name: str
    parameters: Dict[str, Any]

    # Class attribute to define what data the process needs
    input_data_type: str = (
        "full_raster"  # Options: "full_raster", "current_rgb", "custom"
    )

    def execute(self, image): ...
