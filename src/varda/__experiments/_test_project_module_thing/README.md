# Workspace Feature

## Overview

The Workspace feature provides functionality for managing project data in Varda, including images, bands, stretches, and ROIs. It serves as a central data manager for the application, allowing other features to access and modify project data through a well-defined API.

## Architecture

The Workspace feature follows the feature-based architecture pattern, with a clear separation between API, implementation, and infrastructure:

```
workspace/
├── api/                    # Public API for other features to use
│   ├── workspace_service.py  # Main service interface
│   └── __init__.py           # Exports public API
├── implementation/         # Implementation of the API
│   ├── workspace_service_impl.py  # Concrete implementation
│   └── __init__.py           # Exports implementation
├── infrastructure/         # Technical implementations
│   ├── project_io.py         # Project I/O handler
│   ├── project_loader.py     # Project loader
│   └── __init__.py           # Exports infrastructure
├── bootstrap.py            # Bootstrap for the feature
└── README.md               # This file
```

## API

The Workspace feature exposes a clear API through the `WorkspaceService` class, which provides methods for managing project data:

- **Project operations**: `get_project_name`, `save_project`, `load_project`
- **Image operations**: `get_image`, `add_image`, `load_new_image`, `create_image`, `remove_image`, `get_all_images`
- **Metadata operations**: `update_metadata`
- **Stretch operations**: `add_stretch`, `remove_stretch`, `update_stretch`
- **Band operations**: `add_band`, `remove_band`, `update_band`
- **Plot operations**: `add_plot`, `get_plots`
- **ROI operations**: `add_roi`, `remove_roi`, `update_roi`, `get_roi`, `get_rois_for_image`, `get_images_for_roi`

The API also includes signal definitions for notifying subscribers of changes to the data:

- `sigDataChanged`: Emitted when data changes, with parameters for index, change type, and change modifier
- `sigProjectChanged`: Emitted when the project as a whole changes

## Usage

### Initializing the Workspace Feature

To initialize the Workspace feature, use the `bootstrap` module:

```python

from varda._test_project_module_thing import bootstrap

# Create the _test_project_module_thing service
workspace_service = bootstrap.create_workspace_service()

# Or register it in a service registry
bootstrap.register_workspace_service(registry, image_loading_service)
```

### Using the Workspace Service

Once initialized, the Workspace service can be used to manage project data:

```python
# Load a project
workspace_service.load_project("path/to/project.varda")

# Get an image
image = workspace_service.get_image(0)

# Add a new image
image_index = workspace_service.create_image(raster, metadata)

# Save the project
workspace_service.save_project()
```

### Subscribing to Changes

To be notified of changes to the project data, connect to the signals:

```python
# Connect to the sigDataChanged signal
workspace_service.sigDataChanged[int, str, str].connect(on_data_changed)

# Connect to the sigProjectChanged signal
workspace_service.sigProjectChanged.connect(on_project_changed)

# Handler for data changes
def on_data_changed(index, change_type, change_modifier):
    print(f"Data changed: {index}, {change_type}, {change_modifier}")

# Handler for project changes
def on_project_changed():
    print("Project changed")
```

## Dependencies

The Workspace feature depends on:

- **Common domain entities**: `Image`, `Metadata`, `Band`, `Stretch`, `Plot`, `ROI`, `Project`
- **PyQt6**: For the signal/slot system
- **Image loading service**: For loading image data

## Migration from ProjectContext

The Workspace feature is a direct replacement for the old `ProjectContext` class, with a cleaner API and better separation of concerns. To migrate from `ProjectContext` to `WorkspaceService`:

1. Replace imports:
   ```python
   # Before
   from varda.project.project_context import ProjectContext
   
   # After
   from varda._test_project_module_thing.api import WorkspaceService
   ```

2. Update method calls:
   ```python
   # Before
   project_context.getImage(index)
   
   # After
   workspace_service.get_image(index)
   ```

3. Update signal connections:
   ```python
   # Before
   project_context.sigDataChanged[int, ProjectContext.ChangeType].connect(handler)
   
   # After
   workspace_service.sigDataChanged[int, str].connect(handler)
   ```

4. Update the application bootstrap as shown in `bootstrap_example.py`