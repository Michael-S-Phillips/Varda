"""
Dual Image View Types and Configuration

Defines enums, data classes, and configuration objects for dual image view functionality.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from PyQt6.QtCore import QObject


class DualImageMode(Enum):
    """Enumeration of dual image display modes"""

    SIDE_BY_SIDE = "side_by_side"
    OVERLAY = "overlay"
    BLINK = "blink"


class LinkType(Enum):
    """Enumeration of image linking types"""

    PIXEL_BASED = "pixel_based"  # Same extent, pixel-to-pixel correspondence
    GEOSPATIAL = "geospatial"  # Linked by geographic coordinates


@dataclass
class DualImageConfig:
    """Configuration settings for dual image view"""

    # Display settings
    mode: DualImageMode = DualImageMode.SIDE_BY_SIDE
    link_type: LinkType = LinkType.PIXEL_BASED

    # Overlay settings
    overlay_opacity: float = 0.5  # 0.0 = fully transparent, 1.0 = fully opaque
    overlay_blend_mode: str = "normal"  # Future: support different blend modes

    # Blink settings
    blink_interval: int = 1000  # milliseconds between blinks
    blink_enabled: bool = False

    # Synchronization settings
    sync_navigation: bool = True  # Sync pan/zoom
    sync_rois: bool = True  # Share ROIs between images
    sync_stretch: bool = False  # Sync stretch settings (optional)
    sync_bands: bool = False  # Sync band selection (optional)

    # Visual settings
    show_link_indicators: bool = True  # Show visual indicators of linked status


@dataclass
class ImagePair:
    """Data class representing a pair of linked images"""

    primary_index: int
    secondary_index: int
    config: DualImageConfig

    # Transformation data for coordinate mapping
    transform_matrix: Optional[Any] = None  # For geospatial transformations
    pixel_offset: Optional[Tuple[int, int]] = None  # For pixel-based offsets

    def __post_init__(self):
        """Validate the image pair configuration"""
        if self.primary_index == self.secondary_index:
            raise ValueError("Primary and secondary images must be different")

    def get_other_index(self, current_index: int) -> Optional[int]:
        """Get the index of the other image in the pair"""
        if current_index == self.primary_index:
            return self.secondary_index
        elif current_index == self.secondary_index:
            return self.primary_index
        return None

    def is_primary(self, index: int) -> bool:
        """Check if the given index is the primary image"""
        return index == self.primary_index
