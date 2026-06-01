# Image Renderer Settings → Parameter System Migration

**Date:** 2026-06-01
**Status:** Design approved, pending spec review

## Motivation

The image renderer's settings (`RendererSettings`) are a plain dataclass driven by
a ~190-line hand-built Qt panel (`RendererSettingsPanel`) that mutates the dataclass
in place. This makes programmatic edits delicate or impossible — in particular:

- Switching the stretch algorithm to "Min-Max (Manual)" from code.
- Setting that manual stretch's min/max values from code.
- Wiring the histogram's region-drag to drive the stretch min/max (currently a TODO,
  blocked because the renderer can't be told to change stretch params).

Varda already has a parameter system (`common/parameter.py`) that auto-generates UI,
groups parameters, and emits change signals. The stretch *algorithms* already expose
their parameters through it (`ManualValueStretchRGB.Config`, `LinearPercentileStretch.Config`
are `ParameterGroup`s). This migration brings the renderer-level settings (mode, bands,
stretch selection, colormap, opacity) onto the same system so the UI is auto-generated
and every setting is programmatically editable.

## Goals

1. Represent `RendererSettings` with the parameter system.
2. Provide a clean programmatic API: a parameter tree **plus** convenience methods on
   `ImageRenderer` for common cases.
3. Wire the histogram region-drag to set the stretch min/max end-to-end.
4. Shrink `RendererSettingsPanel` to mostly composing auto-generated param widgets.

## Non-Goals

- New stretch algorithms (Gaussian, log, etc. — still TODO elsewhere).
- Reworking viewports, ROI system, or the rendering math itself.
- A fully generic "auto-rendering switchable group" parameter type. Where one
  parameter must drive another's visibility (mode → bands/colormap), the panel
  coordinates it explicitly.

## Current State (for reference)

- `RendererSettings` dataclass: `image`, `mode` (`"mono"`/`"rgb"` str), `bands` (np array),
  `stretch` (StretchAlgorithm instance), `colorMap` (`pg.ColorMap`), `opacity` (float).
- `ImageRenderer`: owns settings, `render()` (cached), `updateSettings(settings)` (swaps
  the whole object, clears cache, emits `sigShouldRefresh`), `getSettingsPanel()`.
  Stub methods `setMinMaxValues`/`manuallySetStretch` do nothing.
- `RendererSettingsPanel`: emits `sigSettingsChanged(RendererSettings)`; mutates the
  dataclass in place; builds mode radios, stacked band combos, colormap gradient, stretch
  combo + stacked stretch-param widgets, opacity slider.
- Consumers of `render()` (viewports, `image_region_item`, vispy experiment) are unaffected
  by the data-model change. Consumers that read `.settings.mode` / mutate `.settings.bands`
  (`new_histogram_view`) need updating.

## Design

### 1. `RendererSettings` becomes a `ParameterGroup`

The renderer **owns and keeps** one settings instance (no more whole-object replacement).
`image` stays a plain attribute (it is the data, not a user-tunable setting).

```python
class RenderMode(Enum):
    MONO = auto()
    RGB  = auto()

class RgbBandGroup(ParameterGroup):
    red   = BandParameter("Red Band")
    green = BandParameter("Green Band")
    blue  = BandParameter("Blue Band")

class MonoViewGroup(ParameterGroup):
    band     = BandParameter("Band")
    colorMap = ColorMapParameter("Color Map")

class RendererSettings(ParameterGroup):
    mode    = EnumParameter("Mode", RenderMode, RenderMode.MONO)
    rgb     = RgbBandGroup()
    mono    = MonoViewGroup()
    stretch = StretchParameter("Stretch Algorithm")
    opacity = FloatParameter("Opacity", 1.0, (0.0, 1.0), "%")

    def __init__(self, image: VardaRaster, parent=None):
        super().__init__(parent)
        self.image = image
        for p in (self.rgb.red, self.rgb.green, self.rgb.blue, self.mono.band):
            p.setImage(image)
        self.stretch.setImage(image)
        # seed defaults from image (e.g. image.defaultBands)
```

Mirrors how `GeneralImageAnalysisConfig` already wires an image-dependent parameter in
`__init__`. Replaces the `RendererSettings.new(image)` factory with `RendererSettings(image)`.

Programmatic access: `settings.stretch`, `settings.rgb.red`, `settings.mono.colorMap`,
`settings.opacity`, `settings.mode`.

### 2. New render-specific parameter types

New module `src/varda/image_rendering/render_parameters.py` (keeps pyqtgraph and
stretch-algorithm dependencies out of the generic `common/parameter.py`):

- **`BandParameter(Parameter[int])`** — value is a band index; widget is a combo of the
  image's wavelengths. Image-aware via `setImage()` (same pattern as
  `ImageParameter.setProvider`). Knows the valid band count from the image.
- **`ColorMapParameter(Parameter[pg.ColorMap])`** — value is a `pg.ColorMap`; widget is the
  `pg.GradientWidget`. The HSV-unsupported guard (currently in the panel) moves here.
- **`StretchParameter(Parameter[StretchAlgorithm])`** — value is the *active* algorithm
  instance. Pre-builds one instance per registry entry; exposes `selectByName(name)`,
  `current`, `optionNames`. Connects each held algorithm's `parameters().sigParameterChanged`
  to its own change signal so editing any stretch sub-param propagates. `setImage()`
  configures the manual stretch's min/max param ranges from the data range.
  Its `getWidget()` returns a **self-contained combo + stacked sub-form** (the stretch combo
  only drives its own sub-params, so no cross-parameter coordination is needed).

### 3. Change propagation

The settings object is stable for the renderer's lifetime. `ImageRenderer` connects once:

```python
self.settings.sigParameterChanged.connect(self._onSettingsChanged)
# _onSettingsChanged: clear cache, emit sigShouldRefresh
```

Any change — from the UI panel *or* a programmatic `param.set(...)` — flows through the
same path. `updateSettings()` is removed (no remaining callers once the panel is migrated).

**Required fix:** `ParameterGroup.__init__` wires child change signals with
`lambda _: self.sigParameterChanged.emit()`. That breaks for child `ParameterGroup`s,
whose `sigParameterChanged` emits no argument. The path is currently untested (no existing
nested groups). This design nests groups (`rgb`, `mono`), so the wiring must be fixed to
handle both `Parameter` children (emit a value) and `ParameterGroup` children (emit nothing).

### 4. `RendererSettingsPanel` (thinner)

Reduces to composing param widgets plus **one** piece of cross-parameter coordination:
a `QStackedLayout` swapped by the `mode` param (RGB group widget ↔ mono group widget).

- `mode`   → `EnumParameter.getWidget()`, plus a slot that swaps the stacked band/colormap area.
- band/colormap → `self.rgb.createWidget()` and `self.mono.createWidget()` in the stack.
- `stretch` → `StretchParameter.getWidget()` (self-contained combo + stacked).
- `opacity` → `FloatParameter.getWidget()`.

The panel no longer mutates a dataclass or emits `sigSettingsChanged`; it edits the live
parameters directly. `getSettingsPanel()` builds a panel bound to the renderer's settings.

### 5. Histogram drag → stretch

`new_histogram_view`'s `LinearRegionItem`s become `movable=True`. On
`sigRegionChangeFinished`, the view calls an `ImageRenderer` convenience method that:

1. Ensures the manual stretch ("Min-Max (Manual)") is active, **seeding** it from the
   current computed min/max so unchanged channels don't jump.
2. Sets the dragged channel's min/max.

Renderer refresh is automatic via the param-change path. Mono drives channel 0; RGB drives
channels 0/1/2.

### 6. Programmatic API

- **Foundation (param tree):** the manual stretch (`ManualValueStretchRGB`) exposes
  per-channel `Vec2Parameter`s (`config.redStretch`/`greenStretch`/`blueStretch`, min in `.x`,
  max in `.y`):
  ```python
  settings.stretch.selectByName("Min-Max (Manual)")
  settings.stretch.current.config.redStretch.set(Vec2(lo, hi))
  ```
- **Convenience on `ImageRenderer`** (replaces the stubbed `setMinMaxValues` /
  `manuallySetStretch`):
  - `setStretchMinMax(channel: int, lo: float, hi: float)` — per-channel (0→red, 1→green,
    2→blue); used by histogram drag.
  - `setManualStretch(lo: float, hi: float)` — all channels to the same range.

  Both ensure the manual stretch is active (seeded from current min/max) before setting.

### 7. Consumer updates

Mostly mechanical:

- `image_renderer.py` — core migration; `render()` reads from params.
- `new_histogram_view.py` — `settings.mode == "mono"` → `settings.mode.get() == RenderMode.MONO`;
  `renderSettings.bands = np.array([0,1,2])` → set band params + mode; add region-drag wiring.
- `general_image_analysis.py`, `dual_image_workspace.py` — use `getSettingsPanel()` only; unaffected
  beyond construction (`RendererSettings.new` → `RendererSettings`, if referenced).
- `imageview_list.py`, `triple_raster_view.py`, `image_viewport.py`, `varda_viewport.py`,
  `image_region_item.py`, `_experiments/vispy_varda_raster_viewer.py` — call `render()` /
  connect `sigShouldRefresh`; unaffected.

## Testing Strategy

The parameter-based model is testable without a GUI:

- `StretchParameter`: `selectByName` sets `current`; sub-param edits emit change signals.
- `ImageRenderer.setManualStretch` / `setStretchMinMax`: activates manual stretch, seeds from
  current min/max, sets the right channel; `render()` output reflects it.
- Nested `ParameterGroup` propagation fix: editing a param inside `rgb`/`mono` emits
  `RendererSettings.sigParameterChanged`.
- `BandParameter`: index ↔ wavelength mapping; respects image band count.

GUI panel wiring (widget swapping on mode) remains harder to unit-test and is verified manually.

## Risks / Open Points

- Nested `ParameterGroup` signal propagation fix may touch behavior relied on elsewhere —
  audit existing `ParameterGroup` users before changing.
- `EnumParameter` renders `RenderMode.RGB` as "Rgb" via its name-prettifier (cosmetic; can
  override display if undesirable).
- Manual stretch is currently RGB-oriented (red/green/blue Vec2 params). Seeding/range-from-data
  must handle both mono (1 channel) and RGB (3 channels) cleanly.
