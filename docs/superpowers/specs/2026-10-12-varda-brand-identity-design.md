# Varda Brand Identity: App and GitHub Integration — Design

**Date:** 2026-10-12
**Status:** Approved (design). The assets are final and already in the repo; this spec
covers wiring them in.
**Phasing:** Phase 1 (icon, splash, README) goes to an implementation plan now. Phase 2
(busy indicator, typeface, About box) is optional and can follow.

## Background

Varda has a new identity. The app icon is a reflectance spectrum shaped like a V, with a
dotted continuum. The wordmark continues that spectrum across the tops of the letters.
Below a halfway cut, the letters are white on dark grounds and ink on light grounds.
Everything was designed and approved on a separate design canvas and exported into
`resources/brand/`. **`resources/brand/README.md` is the brand guide**: it covers the file
index, colors, type, clear space and minimum sizes. Read it before starting.

Today the app uses `resources/logo.svg` in three places:

- `main.py` sets it as the window icon.
- `main.py` shows `QSplashScreen(QPixmap(ICON_PATH))`, so the splash is just the old
  square logo at whatever size `QPixmap` gives an SVG.
- `scripts/generate_icons.py` rasterizes it into `logo.ico` and `logo.icns`, which
  `Varda.spec` hands to PyInstaller.

The README opens with a plain `# Varda` heading.

## What is already in the repo (do not regenerate or hand-edit)

```
resources/brand/
  README.md                        brand guide
  icon/        varda-icon.svg (ink tile, 512), varda-icon-macos.svg (Apple 1024 grid),
               varda-icon-paper.svg, varda-mark-on-dark.svg, varda-mark-on-light.svg
  wordmark/    varda-wordmark-{on-dark,on-light,small-on-dark,small-on-light,mono-white,mono-ink}.svg
  lockup/      varda-lockup-{on-dark,on-light}.svg
  splash/      varda-splash.svg, varda-splash-tagline.svg, splash-motion.json
  loader/      loader-motion.json, varda-loader-web-{on-dark,on-light}.svg
  fonts/       PoiretOne-Regular.ttf, OFL.txt
docs/assets/
  varda-hero-on-dark.svg, varda-hero-on-light.svg   animated README header (plays once, then holds)
  varda-social-preview.png                          1280×640
```

All static SVGs are **Qt-safe**. `QSvgRenderer` ignores `clipPath`, masks, filters, CSS
and animation, so these files use none of them. Each was checked with PyQt6 6.10
`QSvgRenderer` against Chromium, and the two match. Load them with `QSvgRenderer` or
`QIcon`. **Do not** load the `docs/assets/varda-hero-*` or `loader/varda-loader-web-*`
files in Qt: they are CSS-animated and for browsers only.

`resources/` is already bundled whole by `Varda.spec`, so the new files ship with
PyInstaller builds with no spec change.

## Scope decisions

- The app icon is `varda-icon.svg` (ink tile). It replaces `resources/logo.svg` in place,
  so `ICON_PATH`, `Varda.spec` and the Windows AppUserModelID stay as they are.
- macOS `.icns` is built from `varda-icon-macos.svg` (Apple's grid: an 824 tile with
  100 px margins). Built from the full-bleed tile, the icon would look oversized in the
  Dock. Windows `.ico` and the window icon use the full-bleed `varda-icon.svg`.
- The splash is the animated draw-on, painted with QPainter from `splash-motion.json`. The
  static `varda-splash.svg` is its last frame and the fallback.
- **The animation must never meaningfully delay startup.** It runs while initialization
  happens. If the main window is ready before the animation ends, wait for it only if
  less than 1.0 s is left; otherwise jump to the last frame and close.
- GitHub: the README header becomes the animated hero, with a light/dark `<picture>`
  switch. Michael uploads the social preview image by hand (see Manual steps).
- No other UI restyling. The brand palette is **not** applied to the app's widgets, plots
  or themes in this work.

## Phase 1

### 1. App icon (`resources/logo.svg`, `scripts/generate_icons.py`)

1. Copy `resources/brand/icon/varda-icon.svg` over `resources/logo.svg`.
2. In `scripts/generate_icons.py`, use separate sources for the two containers:
   - `ICO_SOURCE = resources/logo.svg` (full-bleed tile)
   - `ICNS_SOURCE = resources/brand/icon/varda-icon-macos.svg`

   Change `render_svg(size)` to `render_svg(svg_path, size)`, and keep the existing size
   lists.
3. Run `uv run python scripts/generate_icons.py` and commit the regenerated `logo.ico` and
   `logo.icns`.
4. Check the 16 and 32 px frames of the `.ico` visually (open them, or dump them to PNG).
   The V and its dots should read cleanly. The design was checked at 16 px.

### 2. Splash (`src/varda/main.py` plus a new module)

Create a small module, for example `src/varda/branding/splash.py`, containing:

- **Pure helpers, with no Qt widgets:** load the JSON spec; a CSS `cubic-bezier` easing
  function; `progress(t, start, end)`; and `partialPolylines(polylines, f0, f1)`, which
  returns the stretch of a polyline chain between arc-length fractions. Unit-test these
  in a colocated `_tests/test_splash_motion.py`. Test the easing endpoints and midpoint
  symmetry, partial lengths, a cut that spans two polylines, and empty output at 0.
- **`paintSplash(painter, spec, brandDir, t, target)`**: paints one frame. The appendix has
  a verified reference implementation. Its frame at t ≥ `timeline.end` matches
  `varda-splash.svg` rendered by `QSvgRenderer`, and the two differ only in antialiasing.
- **`AnimatedSplash(QSplashScreen)`**:
  - It takes a `QPixmap` of logical size 640×360 at the screen's `devicePixelRatio`.
  - On a ~60 fps `QTimer`, it repaints by drawing `paintSplash` into the pixmap (or by
    overriding `drawContents`), with t taken from a `QElapsedTimer`.
  - `finishWhenDone(window)` applies the 1.0 s rule from Scope decisions, then calls
    `finish(window)`.

Paint order and parameters all come from the JSON: `paintOrder`, `strokeWidth`,
`gradient` (a horizontal `QLinearGradient` in the same user units), the `trace.clipOut`
rectangles, and the timeline. **Do not hard-code geometry.** In outline:

| Element | Behavior |
|---|---|
| `lowerHalves` | Paper-colored polylines with flat caps, plus discs for the round baseline ends. Each letter fades in over its window. |
| `dots` | Four continuum dots that pop in one after another. |
| `v` | Draws on along its length (`easing`). |
| `trace` | One draw-on across both polylines in order, by arc length, with the `clipOut` rectangles excluded so its round ends stop flat at the cut. |
| `tagline` | `varda-splash-tagline.svg` rendered over the whole viewBox, fading in while rising 40 units. |

The whole sequence takes 2.3 s.

`initVarda()` changes:

- Build the splash right after `QApplication`.
- Call `q_app.processEvents()` between the existing init stages, because all the init
  work runs on the main thread and blocks the timer. The stages are: after logging init,
  after `VardaApplication()` and plugins, after `MainGUI(...)`, and after
  `showMaximized()`.
- Replace `splash.finish(app.maingui)` with `splash.finishWhenDone(app.maingui)`.
- Keep a static path: if the environment variable `VARDA_STATIC_SPLASH=1` is set, or the
  JSON fails to load, render `varda-splash.svg` with `QSvgRenderer` into the HiDPI pixmap
  and use a plain `QSplashScreen`. The static splash should also replace today's
  `QPixmap(ICON_PATH)`, which renders the SVG at its intrinsic size.

### 3. GitHub README

Replace the opening `# Varda` line with:

```html
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/varda-hero-on-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/varda-hero-on-light.svg">
    <img alt="Varda: visualization and analysis of raster data" src="docs/assets/varda-hero-on-light.svg" width="640">
  </picture>
</p>
```

Leave the rest of the README unchanged. The hero draws on once in about 2.6 s, holds, and
shows the final frame under reduced motion. GitHub plays CSS animation in SVGs referenced
with `<img>`.

### 4. CLAUDE.md

Under Key Patterns, add one line: "Brand assets and rules: `resources/brand/README.md`.
Use the files there as-is, and load static SVGs with QSvgRenderer, never the
CSS-animated ones."

## Phase 2 (optional)

- **Busy indicator.** Add a `SpectrumBusyIndicator(QWidget)` that paints
  `loader-motion.json` (`paintLoader` in the appendix). Its sizes are 24, 48 and 128 px.
  At ≤24 px it uses stroke 56 and drops the track. Use it **only for indeterminate
  waits**: a `QProgressDialog`/`QProgressBar` with range (0, 0), or a wait whose length is
  unknown before the first progress tick. Candidates to check:
  - `image_loading/image_loading_service.py` (QProgressDialog near l.199)
  - `analysis/runner.py` (near l.65)
  - `image_loading/export_image_dialog.py` (near l.124)
  - the spectral hourglass status-bar `progressBar`

  Leave determinate progress bars alone.
- **Typeface.** Register `resources/brand/fonts/PoiretOne-Regular.ttf` with
  `QFontDatabase.addApplicationFont` at startup. Use it only for display text (an About
  box title, large empty-state headings), never for widgets, tables or numbers. Keep
  `OFL.txt` next to the font, as the license requires.
- **About box.** Add Help → About Varda: `varda-lockup-on-dark.svg` (or `-on-light` to
  match the palette), the version from `importlib.metadata.version("varda")`, and links to the
  repo and Releases.

## Manual steps (Michael, on GitHub)

- Settings → General → Social preview: upload `docs/assets/varda-social-preview.png`.
- Optionally, set the repository "About" description to "Visualization and analysis of
  raster data (hyperspectral and multispectral)".

## Acceptance checks

- `uv run python scripts/generate_icons.py` writes both containers. The `.ico` has 7
  frames (16–256) and the `.icns` goes to 1024. The new V shows in the Dock, the taskbar
  and the window title bar.
- `uv run varda` shows the animated splash, which reaches its final frame or closes
  within the rule above. The main window opens no more than 1.0 s later than before.
  `VARDA_STATIC_SPLASH=1` shows the static splash.
- The new helper tests pass, and `uv run pytest`, `uv run ruff format`,
  `uv run ruff check` and `uv run ty check` are all clean.
- A PyInstaller build (`uv run pyinstaller Varda.spec`) launches with the new icon and
  splash (the assets are bundled through `resources/`).
- On GitHub the README header switches with the light/dark theme and animates once.

## Appendix: reference painter (verified)

Adapt this into `src/varda/branding/splash.py`, keeping the repo conventions (camelCase
in Qt-facing code, type hints, no `Any`). Frames rendered with it match the static SVG
at t ≥ 2.3 s.

```python
"""Reference painter for resources/brand/splash/splash-motion.json and loader/loader-motion.json."""

import json
import math
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtSvg import QSvgRenderer

Point = tuple[float, float]


def cubicBezierEase(x1: float, y1: float, x2: float, y2: float):
    """CSS cubic-bezier() timing function: maps time fraction -> progress."""

    def ease(t: float) -> float:
        if t <= 0.0:
            return 0.0
        if t >= 1.0:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(40):  # solve x(s) = t by bisection
            s = (lo + hi) / 2
            x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s**3
            lo, hi = (s, hi) if x < t else (lo, s)
        s = (lo + hi) / 2
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s**3

    return ease


def progress(t: float, start: float, end: float) -> float:
    return min(1.0, max(0.0, (t - start) / (end - start)))


def partialPolylines(polylines: list[list[Point]], f0: float, f1: float) -> list[list[Point]]:
    """The stretch of a chain of polylines between arc-length fractions f0..f1 (0..1)."""
    total = sum(math.dist(a, b) for poly in polylines for a, b in zip(poly, poly[1:]))
    s0, s1 = f0 * total, f1 * total
    out: list[list[Point]] = []
    walked = 0.0
    for poly in polylines:
        piece: list[Point] = []
        for a, b in zip(poly, poly[1:]):
            length = math.dist(a, b)
            lo, hi = walked, walked + length
            walked = hi
            if length == 0 or hi < s0 or lo > s1:
                continue
            ta, tb = max(0.0, (s0 - lo) / length), min(1.0, (s1 - lo) / length)
            pa = (a[0] + (b[0] - a[0]) * ta, a[1] + (b[1] - a[1]) * ta)
            pb = (a[0] + (b[0] - a[0]) * tb, a[1] + (b[1] - a[1]) * tb)
            if not piece:
                piece.append(pa)
            piece.append(pb)
        if len(piece) > 1:
            out.append(piece)
    return out


def toPath(poly: list[Point]) -> QPainterPath:
    path = QPainterPath(QPointF(*poly[0]))
    for x, y in poly[1:]:
        path.lineTo(x, y)
    return path


def spectrumBrush(g: dict) -> QBrush:
    gradient = QLinearGradient(g["x1"], 0, g["x2"], 0)
    for offset, color in g["stops"]:
        gradient.setColorAt(offset, QColor(color))
    return QBrush(gradient)


def paintSplash(p: QPainter, spec: dict, brandDir: Path, t: float, target: QRectF) -> None:
    """Paint the splash at time t (seconds) into target. Call with antialiasing on."""
    x, y, w, h = spec["viewBox"]
    tl = spec["timeline"]
    sw = spec["strokeWidth"]
    p.save()
    p.fillRect(target, QColor(spec["background"]))
    p.translate(target.topLeft())
    p.scale(target.width() / w, target.height() / h)
    p.translate(-x, -y)

    # 1. lower halves (fade in as the trace passes each letter)
    lower = spec["lowerHalves"]
    for name, group in lower["groups"].items():
        opacity = progress(t, *tl["lowerHalves"][name])
        if opacity <= 0:
            continue
        p.setOpacity(opacity)
        color = QColor(lower["color"])
        p.setPen(QPen(color, sw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin))
        for poly in group["polylines"]:
            p.drawPath(toPath(poly))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        for cx, cy in group["discs"]:
            p.drawEllipse(QPointF(cx, cy), sw / 2, sw / 2)
        p.setBrush(Qt.BrushStyle.NoBrush)

    # 2. continuum dots (pop: scale 0 -> 1.4 -> 1, opacity 0 -> 0.8 -> final)
    dots, dt = spec["dots"], tl["dots"]
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(dots["color"]))
    for i, (cx, cy) in enumerate(dots["centers"]):
        start = dt["popStart"] + i * dt["stagger"]
        u = progress(t, start, start + dt["pop"])
        if u <= 0:
            continue
        peak = 0.57
        scale = 1.4 * u / peak if u < peak else 1.4 - 0.4 * (u - peak) / (1 - peak)
        p.setOpacity(0.8 * u / peak if u < peak else 0.8 - (0.8 - dots["opacity"]) * (u - peak) / (1 - peak))
        r = dots["radius"] * scale
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.setOpacity(1.0)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 3. the V, then 4. the trace (clipped so its loose ends stop flat at the cut)
    p.setPen(QPen(spectrumBrush(spec["gradient"]), sw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    for key, polylines in (("v", [spec["v"]["polyline"]]), ("trace", spec["trace"]["polylines"])):
        f = cubicBezierEase(*tl[key]["easing"])(progress(t, *tl[key]["draw"]))
        if f <= 0:
            continue
        if key == "trace":
            clip = QPainterPath()
            clip.addRect(QRectF(x, y, w, h))
            for rect in spec["trace"]["clipOut"]:
                hole = QPainterPath()
                hole.addRect(QRectF(*rect))
                clip = clip.subtracted(hole)
            p.setClipPath(clip)
        for piece in partialPolylines(polylines, 0.0, f):
            p.drawPath(toPath(piece))
        p.setClipping(False)

    # 5. tagline (fade in while rising into place)
    tg = tl["tagline"]
    u = cubicBezierEase(*tg["easing"])(progress(t, *tg["fadeIn"]))
    if u > 0:
        p.setOpacity(u)
        QSvgRenderer(str(brandDir / "splash" / spec["tagline"]["svg"])).render(p, QRectF(x, y + tg["rise"] * (1 - u), w, h))
    p.restore()


def paintLoader(p: QPainter, spec: dict, t: float, target: QRectF, onDark: bool = True) -> None:
    """Paint the busy indicator at time t (seconds) into a square target."""
    px = target.width()
    sw = spec["strokeWidthAtOrBelow24px"] if px <= 24 else spec["strokeWidth"]
    poly = spec["polyline"]
    p.save()
    p.translate(target.topLeft())
    p.scale(px / 512, px / 512)
    if px > 24:  # faint track under the moving stroke
        track = spec["track"]["onDark" if onDark else "onLight"]
        color = QColor(track["color"])
        color.setAlphaF(track["opacity"])
        p.setPen(QPen(color, sw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(toPath(poly))
    ease = cubicBezierEase(0.65, 0, 0.35, 1)
    phase = (t % spec["period"]) / spec["period"]
    f0, f1 = (0.0, ease(phase * 2)) if phase < 0.5 else (ease(phase * 2 - 1), 1.0)
    if f1 - f0 > 1e-4:
        p.setPen(QPen(spectrumBrush(spec["gradient"]), sw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for piece in partialPolylines([poly], f0, f1):
            p.drawPath(toPath(piece))
    p.restore()
```
