# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Varda is a PyQt6 desktop application for visualizing and analyzing hyperspectral and multispectral image data. Users can load images, examine ROIs (regions of interest), view pixel spectra, and adjust band parameters. The app is designed to be very modular and extendible.

Right now, there are some systems that are in an incomplete state and should generally be ignored for now. This includes the plugin system, and image processing system.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run varda

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_core/test_entities.py

# Run a specific test
uv run pytest tests/test_core/test_entities.py::TestClassName::test_method

# Format code
uv run black src/

# Check formatting without modifying
uv run black --check src/

# Type checking
uv run mypy src/
```

## Architecture

### Entry Point and Application Bootstrap

`src/varda/main.py` → `main()` → `initVarda()`: Performs all Application Initialization, Creates `QApplication`, initializes `VardaApplicationContext`, loads plugins, then launches `MainGUI`.

Right now, there is not a strongly defined "Project" data model; Because it's not yet clear what data will need to be stored in a project. So it's kept lightweight; just a list of opened images that the VardaApplicationContext stores.

We also try to do as much wiring as possible at this initialization stage, to reduce dependencies in the GUI code. (Eg. we define actions for creating new workspaces, including the code that sends new workspaces to the MainGUI to create tabs for them, so MainGUI doesn't need to link those things itself, just manage the tabs).

### Source Layout (`src/varda/`)

## Important

- **`image_loading/`** — Pluggable image loaders behind `ImageLoaderProtocol`. `ImageLoadingService` runs loading in background threads.
- **`image_rendering/`** — Systems related to visualization of images. `image_renderer.py` converts gets rgb image from spectral image based on settings. `stretch_algorithms.py` contains band stretch implementations (min-max, linear percentile, etc). `raster_view/` has the widgets to display the results from the image renderer, and other supporting classes for viewport tools, linked viewports, etc.
- **`rois/`** — ROI graphics item (`VardaROI`), management widgets, table model/view, property editor, statistics dialog. **Much of this is outdated because it is dependent on the old ProjectContext.**
- **`common/`** — Shared data types and widgets that are used in many places: `entities.py` (Spectrum, Image, Metadata, ROI domain objects), `parameter.py` (parameter system), `ui.py` (common widgets).
- **`workspaces/`** — Workspace views: `dual_image_workspace/` (side-by-side comparison), `general_image_analysis/` (standard analysis view).
- **`utilities/`** — Helpers: threading, signal utils, debug tools, etc..
- **`maingui.py`** — `MainGUI` (QMainWindow): tabbed workspaces, child window management, docking.

## Incomplete/On-Hold

- **`image_processing/`** — Processing algorithms (decorrelation stretch, normalization). `ImageProcessRegistry` registers available algorithms. `process_controls/` provides UI controls.
    - image processing is on-hold for now, but will be important later.
- **`plugins/`** — Plugin system using `pluggy`. Hooks defined in `_hooks.py` (`onLoad`, `onUnload`). User plugins live in `plugins/user_plugins/` or register via entry points.
    - The plugin system is on-hold until the core application is more established.

## Key Patterns

- **Application-level Actions** are defined in main.py on startup, and dynamically added to the MenuBar.
- **Qt signals/slots** are used throughout for reactive UI updates. psygnal can also be used to create signals and slots in code that doesn't directly depend on Qt.
- **Numba** (`@njit`) may be used in performance-critical paths like stretch algorithms.
- **Background threading** via `ImageLoadingService` for non-blocking image loads.

### Similar Projects

The design goals of Varda are similar to **ENVI Classic**, and **Napari**. Consider using them as references.

## Code Style and Conventions

- **Use type hints** as much as possible, so that MyPy is useful.
- **Variable/Function Naming:** When subclassing classes from Qt, use camelCase for variables and functions. Modules that are completely independent of Qt may use snake_case.
- **Tests** can be colocated with the modules they're testing, using the name test\_\*.py
- **Formatter:** Black
- **Python version:** 3.13.x (as specified in `pyproject.toml`)
- **Package manager:** `uv`
- **Qt tests** run in offscreen mode (`QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py`)

## Note on Testing

Varda currently lacks very much unit testing, due to GUI code being difficult to test.
Moving forward we should try to better seperate GUI and logic, and write unit tests for the logic code.

## CI Checks (PR to main/development)

- Black formatting check
- testing with pytest / pytest-qt
