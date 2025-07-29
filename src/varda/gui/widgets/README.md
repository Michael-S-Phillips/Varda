# Image Process Menu System

This module provides a system for creating menus and actions for registered image processes in the Varda application.

## Features

- Creates QMenus/Actions for all registered image processes
- Organizes processes by category based on the process name (e.g., "my category/my process")
- Displays a dialog for parameter editing when a process is selected
- Integrates with the MainMenuBar

## Usage

### Registering a Process

To register a process that will appear in the menu:

1. Create a class that implements the `ImageProcess` protocol:

```python
class MyProcess:
    # Name with category path (categories separated by '/')
    name = "My Category/My Process"
    
    # Parameters dictionary mapping parameter names to their details
    parameters = {
        "parameter_name": {
            "type": float,  # or bool, int, etc.
            "default": 1.0,
            "min": 0.1,     # optional for numeric types
            "max": 10.0,    # optional for numeric types
            "description": "Description of the parameter",
        },
        # More parameters...
    }
    
    # Type of input data required
    input_data_type = "full_raster"  # or "current_rgb", "custom"
    
    def execute(self, image, parameter_name=1.0):
        # Process the image using the parameters
        # ...
        return processed_image
```

2. Register the process with the registry:

```python
import varda

@varda.plugins.hookimpl
def onLoad():
    varda.app.registry.registerImageProcess(MyProcess)
```

### Process Categories

The `name` attribute of a process can include category information using the '/' separator:

- "My Process" - No category, appears directly in the Process menu
- "My Category/My Process" - Single category level
- "Parent Category/Child Category/My Process" - Nested categories

The menu system will automatically create the necessary category menus.

### Process Parameters

The `parameters` attribute should be a dictionary mapping parameter names to their details:

- `type`: The Python type of the parameter (float, bool, etc.)
- `default`: The default value of the parameter
- `min`, `max`: Optional minimum and maximum values for numeric types
- `description`: A description of the parameter

The dialog will create appropriate widgets based on the parameter type:
- `float`: QDoubleSpinBox
- `bool`: QCheckBox

### Integration with MainMenuBar

The image process menu system is automatically integrated with the MainMenuBar through the `_initProcessMenu` method.

## Example

```python
import varda
import logging

logger = logging.getLogger(__name__)

@varda.plugins.hookimpl
def onLoad():
    logger.info("Plugin hook implementation called")
    varda.app.registry.registerImageProcess(MyProcess)

class MyProcess:
    name = "My Category/My Process"
    parameters = {
        "scale_factor": {
            "type": float,
            "default": 1.0,
            "min": 0.1,
            "max": 10.0,
            "description": "Scale factor to apply to the image",
        },
        "invert": {
            "type": bool,
            "default": False,
            "description": "Whether to invert the image",
        }
    }
    input_data_type = "full_raster"

    def execute(self, image, scale_factor=1.0, invert=False):
        # Apply scaling
        result = image * scale_factor
        
        # Apply inversion if requested
        if invert:
            result = 1.0 - result
            
        return result
```