# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Varda is a PyQt6 desktop application for visualizing and analyzing hyperspectral and multispectral image data. Users can load images, examine ROIs (regions of interest), view pixel spectra, and adjust band parameters. The app is designed to be very modular and extendible.

Right now, the image processing system (`image_processing/`) is incomplete and should generally be ignored for now; analyses live in `analysis/`.

## Dev Tools
uv used for package management. ruff for formatting. ty for static type checking. pytest for unit testing.
When using Astral tools (uv, ty, ruff), invoke the relevant /astral:<skill> to ensure best practices are followed.

## Commands
- **Install/sync deps:** `uv sync`
- **Run the app:** `uv run varda` (entry point `varda.main:main`)
- **Run all tests:** `uv run pytest`
- **Run one test file / test:** `uv run pytest src/varda/image_rendering/_tests/test_foo.py` or `... -k "test_name"`. Tests are colocated in `_tests/` folders as `test_*.py`.
- **Format:** `uv run ruff format` — **Lint:** `uv run ruff check` (add `--fix` to autofix)
- **Type check:** `uv run ty check`
- **Build standalone bundle:** `uv run pyinstaller Varda.spec`; check it with `dist/Varda/Varda --self-test` (`self_test.py`; release builds run it on every platform)

Requires Python 3.13. GUI tests use `pytest-qt`.
## Architecture

### Entry Point and Application Bootstrap

`src/varda/main.py` → `main()` → `initVarda()`: Performs all Application Initialization, Creates `QApplication`, initializes `VardaApplicationContext`, loads plugins, then launches `MainGUI`.

Right now, there is not a strongly defined "Project" data model; Because it's not yet clear what data will need to be stored in a project. So it's kept lightweight; just a list of opened images that the VardaApplicationContext stores.

We also try to do as much wiring as possible at this initialization stage, to reduce dependencies in the GUI code. (Eg. we define actions for creating new workspaces, including the code that sends new workspaces to the MainGUI to create tabs for them, so MainGUI doesn't need to link those things itself, just manage the tabs).

### Source Layout (`src/varda/`)

## Important

- **`image_loading/`** — Pluggable image loaders behind `ImageLoaderProtocol`. `ImageLoadingService` runs loading in background threads.
- **`image_rendering/`** — Systems related to visualization of images. `image_renderer.py` calculates an rgb image from based on settings. `stretch_algorithms.py` contains band stretch implementations (min-max, linear percentile, etc). `raster_view/` has the widgets to display the results from the image renderer, and other supporting classes for viewport tools, linked viewports, etc.
- **`rois/`** — ROI graphics item (`VardaROI`), management widgets, table model/view, property editor, statistics dialog. **Much of this is outdated and should be ignored. We will be rewriting it.**
- **`common/`** — Shared code that is used in many places: `entities.py` (important domain objects such as VardaRaster), `parameter.py` (typed settings as plain psygnal state, no Qt; groups inherit their bases' parameters; a `LabeledEnum`'s values are its UI labels) and `parameter_widgets.py` (the widgets that edit them: `parameterWidget`, `groupWidget`; register new parameter widgets with `@widgetFor`), `ui.py` (useful widgets and builders).
- **`analysis/`** — the Processing menu's analyses, registered in `registry.py` (menu order). Spatial tools that work band by band subclass `bandwise.BandwiseAnalysis` (All bands / One band, no-data filled while filtering); class map tools read and write the `Class` band + `classes`/`classColors` metadata (`class_tools.classRaster`).
- **`workspaces/`** — Workspace views: `dual_image_workspace/` (side-by-side comparison), `general_image_analysis/` (standard analysis view).
- **`utilities/`** — Helpers: background work, signal utils, debug tools, etc. Run anything slow through `background.runInBackground` (results and failures come back on the GUI thread; wrap progress callbacks with `onMainThread`), never a hand-made QRunnable or QThread.
- **`plugins/`** + **`api.py`** — Plugin system (pluggy). Plugins are folders with `plugin.toml` installed into the app-data `plugins` folder (Plugins menu: Manage, Install from Folder/Zip); they import only `varda.api` (the stable, versioned plugin API) and add analyses (`registerAnalyses`) or file formats (`registerDataSources`). `plugin_manager.py` loads/enables/removes them; `app_sink.py` puts their contributions into the menus. Guide: `docs/plugins/authoring.md`. Design incl. AI-built plugins (Kindle a Feature): `docs/superpowers/specs/2026-10-14-ai-plugins-design.md`.
- **`kindling/`** — Kindle a Feature: `providers.py` (the AI behind a small Conversation Protocol; Anthropic first), `agent.py` (the tool-use loop and system prompt), `tools.py` (the model's tools, confined to the plugin's folder), `docs.py` (the authoring guide, a `varda.api` reference generated from the module, the examples; bundled from `docs/plugins`), `checks.py` + `check_worker.py` (the plugin runs in a separate Varda process, `Varda --check-plugin`, on a synthetic cube and a crop of the image; plus an advisory static scan), `ai_settings.py` (API key in the OS keychain via `keyring`), and the two dialogs. Tests use a scripted provider (`_tests/fakes.py`) and an in-memory keyring.
- **`maingui.py`** — `MainGUI` (QMainWindow): tabbed workspaces, child window management, docking.

## Incomplete/On-Hold

- **`image_processing/`** — Processing algorithms (decorrelation stretch, normalization). `ImageProcessRegistry` registers available algorithms. `process_controls/` provides UI controls.
    - image processing is on-hold for now, but will be important later.


## Key Patterns

- **Brand assets and rules:** `resources/brand/README.md`. Use the files there as-is, and load static SVGs with QSvgRenderer, never the CSS-animated ones.
- **Simplicity/Conciseness** is always preferred, and an emphasis on high code quality and maintainability. Declarative patterns are also preferred for this purpose.
- **Application-level Actions** are defined in main.py on startup, and dynamically added to the MenuBar.
- **Qt signals/slots** are used throughout for reactive UI updates. psygnal can also be used to create signals and slots in code that doesn't directly depend on Qt.
- **Numba** (`@njit`) may be used in performance-critical paths like stretch algorithms.

### Similar Projects

The design goals of Varda are similar to **ENVI Classic**, and **Napari**. Consider using them as references.

## Code Style and Conventions

- **American English** in all prose: docs, the changelog, UI text, comments and docstrings (color, center, gray, analyze, normalize, canceled). Data values that must match external tools stay as they are (e.g. PROJ's unit name "metre").
- **Use type hints** as much as possible. but NEVER USE "Any" as a type. If you cannot provide a type hint for some reason then don't put anything.
- **Avoid Lazy Importing**, as it worsens readability.
- **Variable/Function Naming:** When subclassing classes from Qt, use camelCase for variables and functions. Modules that are completely independent of Qt may use snake_case.
- **Tests** can be colocated with the modules they're testing in a subfolder called /\_tests, with filenames test\_\*.py
- **Package manager:** `uv`

## Note on Testing

Varda currently lacks much unit testing, due to GUI code being difficult to test.
Moving forward we should try to better seperate GUI and logic, and write unit tests for the logic code.
