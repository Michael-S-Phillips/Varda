# Varda Feature-Based Architecture Proposal

## Introduction

This document proposes a reorganization of the Varda codebase from its current layered architecture to a feature-based modular monolith. The goal is to create a structure that better "screams" what the program does and provides clear APIs between features.

## Current Architecture

Varda currently follows a layered architecture with top-level packages:

```
varda/
├── app/                    # Application services
├── core/                   # Domain entities and business logic
├── features/               # UI features and components
├── gui/                    # Core UI framework
├── infrastructure/         # Technical services
├── plugins/                # Plugin system
├── resources/              # Static resources
└── _tests/                 # Internal tests
```

This organization separates code by technical concerns rather than by business capabilities. While this provides a clear separation of layers, it has several drawbacks:

1. It's difficult to understand what the application does by looking at the structure
2. Changes to a single feature often require modifications across multiple packages
3. Dependencies between features are not explicit
4. It's challenging to maintain boundaries between features

## Proposed Architecture: Feature-Based Organization

I propose reorganizing the codebase into a feature-based structure:

```
varda/
├── common/                 # Shared code used across features
│   ├── domain/             # Core domain entities
│   ├── ui/                 # Shared UI components
│   └── utils/              # Utility functions
├── features/               # Feature modules
│   ├── image_management/   # Image loading, saving, management
│   ├── image_viewing/      # Image display and navigation
│   ├── band_management/    # Spectral band selection and manipulation
│   ├── roi_analysis/       # Region of interest tools
│   ├── geo_referencing/    # Geospatial referencing
│   ├── image_enhancement/  # Stretching and enhancement
│   ├── plotting/           # Data visualization
│   └── workspace/          # Project and workspace management
├── platform/               # Platform services
│   ├── plugin_system/      # Plugin infrastructure
│   ├── registry/           # Service registry
│   └── threading/          # Threading utilities
├── app/                    # Application bootstrap and composition
├── resources/              # Static resources
└── tests/                  # Tests organized by feature
```

## Feature Module Structure

Each feature module follows a consistent internal structure:

```
features/image_management/
├── api/                    # Public API for other features to use
│   ├── image_loader.py     # Interface for image loading
│   └── image_service.py    # Service for image operations
├── domain/                 # Feature-specific domain entities
│   └── image_metadata.py   # Image metadata specific to this feature
├── infrastructure/         # Technical implementations
│   ├── envi_loader.py      # ENVI format loader
│   └── hdf5_loader.py      # HDF5 format loader
├── ui/                     # User interface components
│   ├── image_list_view.py  # List view of loaded images
│   └── load_dialog.py      # Image loading dialog
└── __init__.py             # Exports public API
```

## Key Principles

1. **Feature Cohesion**: All code related to a specific feature is grouped together
2. **Explicit APIs**: Each feature exposes a clear API for other features to use
3. **Encapsulated Implementation**: Implementation details are hidden within the feature
4. **Dependency Management**: Dependencies between features are explicit and controlled
5. **Testability**: Features can be tested in isolation

## Feature APIs

Each feature module exposes a clear API through its `api` package. This API consists of:

1. **Interfaces**: Protocols/interfaces that define the feature's capabilities
2. **Services**: Classes that provide the feature's functionality
3. **Models**: Data structures that are part of the public API

Example API for the `image_management` feature:

```python
# features/image_management/api/image_service.py
from typing import Protocol, Optional
from pathlib import Path
import numpy as np

from varda.common.domain import Image, Metadata

class ImageLoadingService(Protocol):
    """Service for loading image data."""
    
    def load_image(self, path: Path) -> tuple[np.ndarray, Metadata]:
        """Load image data and metadata from a file."""
        ...
    
    def load_metadata_only(self, path: Path) -> Metadata:
        """Load only metadata from a file."""
        ...

class ImageService:
    """Implementation of the image service."""
    
    def __init__(self, registry):
        self._registry = registry
    
    def load_image(self, path: Path) -> tuple[np.ndarray, Metadata]:
        """Load image data and metadata from a file."""
        loader = self._get_loader(path)
        raster = loader.load_raster_data(path)
        metadata = loader.load_metadata(raster, path)
        return raster, metadata
    
    def load_metadata_only(self, path: Path) -> Metadata:
        """Load only metadata from a file."""
        loader = self._get_loader(path)
        # Implementation details...
        return metadata
    
    def _get_loader(self, path: Path):
        """Get the appropriate loader for the file type."""
        # Implementation details...
```

## Dependencies Between Features

Dependencies between features are managed through their APIs. Features can only depend on the public APIs of other features, not on their internal implementation details.

Example of a feature depending on another feature:

```python
# features/roi_analysis/api/roi_service.py
from varda.features.image_viewing.api import ImageViewService
from varda.common.domain import ROI

class ROIService:
    """Service for ROI analysis."""
    
    def __init__(self, image_view_service: ImageViewService):
        self._image_view_service = image_view_service
    
    def create_roi(self, x: int, y: int, width: int, height: int) -> ROI:
        """Create a new ROI on the current image."""
        current_image = self._image_view_service.get_current_image()
        # Implementation details...
        return roi
```

## Common Code

The `common` package contains code that is shared across multiple features:

1. **Domain**: Core domain entities used by multiple features
2. **UI**: Shared UI components and utilities
3. **Utils**: General utility functions

This package should be kept minimal and only include code that is truly shared across features.

## Platform Services

The `platform` package contains infrastructure services that support the application as a whole:

1. **Plugin System**: Infrastructure for loading and managing plugins
2. **Registry**: Service registry for dependency injection
3. **Threading**: Utilities for background processing

These services are not specific to any feature but provide platform capabilities used by multiple features.

## Application Composition

The `app` package is responsible for bootstrapping the application and composing the features:

1. **Dependency Injection**: Wiring up feature dependencies
2. **Configuration**: Loading application configuration
3. **Startup**: Application startup sequence

This package is the entry point for the application and orchestrates the interaction between features.

## Migration Strategy

Migrating from the current architecture to the proposed feature-based architecture will require careful planning. I recommend a phased approach:

1. **Identify Features**: Identify the main features of the application
2. **Define APIs**: Define clear APIs for each feature
3. **Refactor Common Code**: Extract truly common code to the `common` package
4. **Migrate Features**: Migrate one feature at a time, starting with the most independent ones
5. **Update Dependencies**: Update dependencies between features to use the new APIs
6. **Refactor Tests**: Reorganize tests to match the new structure

## Benefits of the New Architecture

1. **Improved Discoverability**: The structure clearly communicates what the application does
2. **Better Maintainability**: Changes to a feature are localized to its package
3. **Explicit Dependencies**: Dependencies between features are clear and controlled
4. **Easier Onboarding**: New developers can understand the application's capabilities by looking at the feature packages
5. **Testability**: Features can be tested in isolation
6. **Extensibility**: New features can be added without modifying existing code

## Conclusion

The proposed feature-based architecture will make the Varda codebase more maintainable, discoverable, and extensible. By organizing code around business capabilities rather than technical concerns, the structure will better reflect what the application does and provide clear boundaries between features.