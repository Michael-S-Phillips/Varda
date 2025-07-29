# Detailed Example: Image Viewing Feature

This document provides a detailed example of how the `image_viewing` feature would be structured in the proposed feature-based architecture. This example illustrates the principles and patterns described in the main architecture proposal.

## Feature Overview

The `image_viewing` feature is responsible for displaying hyperspectral images and allowing users to navigate, zoom, and interact with them. It includes:

- Displaying raster data with appropriate color mapping
- Handling regions of interest (ROIs)
- Supporting coordinate transformations
- Managing the viewport and navigation

## Directory Structure

```
features/image_viewing/
├── api/                    # Public API
│   ├── image_view_service.py  # Main service interface
│   ├── viewport_protocol.py   # Viewport interface
│   └── __init__.py            # Exports public API
├── domain/                 # Feature-specific domain entities
│   ├── viewport_state.py      # Viewport state model
│   └── view_transform.py      # Coordinate transformation
├── infrastructure/         # Technical implementations
│   └── coordinate_mapper.py   # Coordinate mapping implementation
├── ui/                     # User interface components
│   ├── image_plot_widget.py   # Main image plot widget
│   ├── image_region_item.py   # Image region display item
│   ├── navigation_controls.py # Zoom/pan controls
│   └── viewport_tools/        # Tools for interacting with the viewport
│       ├── pan_tool.py        # Pan tool
│       ├── zoom_tool.py       # Zoom tool
│       └── tool_registry.py   # Registry for viewport tools
└── __init__.py             # Exports public API
```

## Public API

The public API of the `image_viewing` feature is defined in the `api` package:

```python
# features/image_viewing/api/image_view_service.py
from typing import Protocol, Optional
import numpy as np
from PyQt6.QtCore import QPointF

from varda.common.domain import Image, Band, Stretch, ROI

class ViewportProtocol(Protocol):
    """Interface for viewport operations."""
    
    def zoom_to_fit(self) -> None:
        """Zoom to fit the entire image in the viewport."""
        ...
    
    def zoom_to_region(self, roi: ROI) -> None:
        """Zoom to a specific region of interest."""
        ...
    
    def set_current_tool(self, tool_name: str) -> None:
        """Set the current interaction tool."""
        ...

class ImageViewService:
    """Service for image viewing operations."""
    
    def __init__(self, viewport: ViewportProtocol):
        self._viewport = viewport
        self._current_image = None
        self._current_band = None
        self._current_stretch = None
    
    def display_image(self, image: Image, band: Optional[Band] = None, 
                     stretch: Optional[Stretch] = None) -> None:
        """Display an image with the specified band and stretch settings."""
        self._current_image = image
        self._current_band = band or image.metadata.defaultBand
        self._current_stretch = stretch or Stretch.createDefault()
        # Implementation details...
        
    def get_current_image(self) -> Optional[Image]:
        """Get the currently displayed image."""
        return self._current_image
    
    def set_band(self, band: Band) -> None:
        """Set the current band configuration."""
        if self._current_image is None:
            return
        self._current_band = band
        # Implementation details...
    
    def set_stretch(self, stretch: Stretch) -> None:
        """Set the current stretch configuration."""
        if self._current_image is None:
            return
        self._current_stretch = stretch
        # Implementation details...
    
    def image_to_screen_coordinates(self, point: QPointF) -> QPointF:
        """Convert image coordinates to screen coordinates."""
        # Implementation details...
        return screen_point
    
    def screen_to_image_coordinates(self, point: QPointF) -> QPointF:
        """Convert screen coordinates to image coordinates."""
        # Implementation details...
        return image_point
```

## UI Components

The UI components implement the visual aspects of the feature:

```python
# features/image_viewing/ui/image_region_item.py
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF

from varda.common.domain import Image, Band, Stretch
from varda.features.image_viewing.domain import ViewTransform

class VardaImageItem(pg.ImageItem):
    """A modification of the pyqtgraph ImageItem for hyperspectral images."""
    
    def __init__(self, image_entity: Image, band: Band = None, stretch: Stretch = None, **kwargs):
        super().__init__(**kwargs)
        
        self._image_entity = image_entity
        self._band = band or image_entity.metadata.defaultBand
        self._stretch = stretch or Stretch.createDefault()
        
        # Region state
        self._roi = None
        self._regional_data = None
        self._coordinate_transform = None
        self._is_showing_region = False
        
        # Update the display
        self.refresh()
    
    def set_roi(self, roi):
        """Set the region to display from the full image."""
        self._roi = roi
        self._is_showing_region = True
        self.refresh()
    
    def clear_roi(self):
        """Clear the region and show the full image."""
        self._roi = None
        self._coordinate_transform = None
        self._is_showing_region = False
        self.refresh()
    
    def set_band(self, band: Band, update=True):
        """Set the band configuration."""
        self._band = band
        if update:
            self.refresh()
    
    def set_stretch(self, stretch: Stretch, update=True):
        """Set the stretch configuration."""
        self._stretch = stretch
        if update:
            self.refresh()
    
    def refresh(self):
        """Refresh the image display with current settings."""
        self._update_image()
    
    def local_to_image(self, point) -> QPointF:
        """Convert local coordinates to full image coordinates."""
        # Implementation details...
        return image_point
    
    def image_to_local(self, point) -> QPointF:
        """Convert full image coordinates to local coordinates."""
        # Implementation details...
        return local_point
```

## Domain Entities

The domain entities specific to this feature:

```python
# features/image_viewing/domain/viewport_state.py
from dataclasses import dataclass
from typing import Optional
from PyQt6.QtCore import QRectF

from varda.common.domain import Image

@dataclass
class ViewportState:
    """Represents the current state of the image viewport."""
    
    current_image: Optional[Image] = None
    visible_rect: Optional[QRectF] = None
    zoom_level: float = 1.0
    current_tool: str = "pan"
```

## Infrastructure

The infrastructure components provide technical implementations:

```python
# features/image_viewing/infrastructure/coordinate_mapper.py
import numpy as np
from PyQt6.QtCore import QPointF, QRectF

class RegionCoordinateTransform:
    """Handles coordinate transformations between image and region spaces."""
    
    def __init__(self, region_rect: QRectF, image_shape: tuple[int, int]):
        self._region_rect = region_rect
        self._image_shape = image_shape
        # Initialize transformation matrices
        # ...
    
    def local_to_global(self, points):
        """Convert local (region) coordinates to global (image) coordinates."""
        # Implementation details...
        return transformed_points
    
    def global_to_local(self, points):
        """Convert global (image) coordinates to local (region) coordinates."""
        # Implementation details...
        return transformed_points
```

## Integration with Other Features

The `image_viewing` feature integrates with other features through their public APIs:

```python
# features/image_viewing/ui/image_plot_widget.py
from PyQt6.QtWidgets import QWidget

from varda.features.image_management.api import ImageService
from varda.features.band_management.api import BandService
from varda.features.image_enhancement.api import StretchService
from varda.features.roi_analysis.api import ROIService

class ImagePlotWidget(QWidget):
    """Widget for displaying and interacting with images."""
    
    def __init__(self, image_service: ImageService, band_service: BandService,
                 stretch_service: StretchService, roi_service: ROIService):
        super().__init__()
        
        self._image_service = image_service
        self._band_service = band_service
        self._stretch_service = stretch_service
        self._roi_service = roi_service
        
        # Initialize UI components
        # ...
    
    def display_image(self, image_id: str):
        """Display an image by its ID."""
        image = self._image_service.get_image(image_id)
        if image is None:
            return
        
        # Get current band and stretch settings
        band = self._band_service.get_current_band(image_id)
        stretch = self._stretch_service.get_current_stretch(image_id)
        
        # Update the display
        self._image_item.set_image(image, band, stretch)
        
        # Notify ROI service about the new image
        self._roi_service.set_current_image(image_id)
```

## Feature Registration and Composition

The feature is registered and composed in the application bootstrap:

```python
# app/bootstrap.py
from varda.features.image_viewing.api import ImageViewService
from varda.features.image_management.api import ImageService
from varda.features.band_management.api import BandService
from varda.features.image_enhancement.api import StretchService
from varda.features.roi_analysis.api import ROIService

def bootstrap_application():
    """Bootstrap the application and compose features."""
    
    # Create services
    image_service = ImageService()
    band_service = BandService()
    stretch_service = StretchService()
    
    # Create viewport
    viewport = create_viewport()
    
    # Create image view service with dependencies
    image_view_service = ImageViewService(viewport)
    
    # Create ROI service with dependency on image view service
    roi_service = ROIService(image_view_service)
    
    # Register services in the registry
    registry = ServiceRegistry()
    registry.register("image_service", image_service)
    registry.register("band_service", band_service)
    registry.register("stretch_service", stretch_service)
    registry.register("image_view_service", image_view_service)
    registry.register("roi_service", roi_service)
    
    return registry
```

## Benefits of This Structure

This feature-based structure provides several benefits:

1. **Clear Responsibility**: The `image_viewing` feature has a clear, focused responsibility.
2. **Explicit API**: The feature exposes a well-defined API for other features to use.
3. **Encapsulation**: Implementation details are hidden within the feature.
4. **Testability**: The feature can be tested in isolation by mocking its dependencies.
5. **Maintainability**: Changes to the feature are localized to its package.

## Conclusion

This detailed example demonstrates how a feature would be structured in the proposed architecture. By organizing code around business capabilities rather than technical concerns, the structure better reflects what the application does and provides clear boundaries between features.