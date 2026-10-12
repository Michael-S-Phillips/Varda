# Brand identity, Phase 1 — implementation plan

**Spec:** `docs/superpowers/specs/2026-10-12-varda-brand-identity-design.md` (Phase 1).
**Brand guide:** `resources/brand/README.md`.
**Branch:** `feature/brand-identity` (off `main`). Assets were committed as-is in `312c5c7`.

Phase 1 is four pieces, done in this order, one commit each: app icon, splash helpers
(pure, tested), the animated splash wired into startup, and the README header plus the
CLAUDE.md line. Phase 2 (busy indicator, typeface, About box) is out of scope.

## 1. App icon

**Files:** `resources/logo.svg`, `scripts/generate_icons.py`, `resources/logo.ico`,
`resources/logo.icns`.

1. Copy `resources/brand/icon/varda-icon.svg` over `resources/logo.svg`. `ICON_PATH`,
   `Varda.spec` and the Windows AppUserModelID stay unchanged.
2. `generate_icons.py`: replace `SVG_PATH` with `ICO_SOURCE = resources/logo.svg` and
   `ICNS_SOURCE = resources/brand/icon/varda-icon-macos.svg`; change
   `render_svg(size)` to `render_svg(svgPath, size)`. Render each container from its own
   source at its largest size, keeping the existing size lists (`.ico` 16–256, 7 frames;
   `.icns` to 1024). Exit with a message if either source is missing.
3. Run `uv run python scripts/generate_icons.py`; commit the regenerated `.ico` and
   `.icns`.
4. Check: open the `.ico` with Pillow, assert 7 frames, and dump the 16 and 32 px frames
   to PNG to look at (the V and dots must read cleanly). Confirm the `.icns` holds a
   1024 image. Nothing here is unit-tested; the script is a one-off tool.

## 2. Splash helpers (pure, no widgets) — TDD

**Files:** new `src/varda/branding/__init__.py`, `src/varda/branding/splash.py`,
`src/varda/branding/_tests/test_splash_motion.py`.

Tests first (`test_splash_motion.py`), then the code adapted from the spec's appendix:

- `cubicBezierEase(x1, y1, x2, y2)`: endpoints 0 → 0 and 1 → 1, clamps outside [0, 1];
  a symmetric curve (e.g. 0.65, 0, 0.35, 1) gives ease(0.5) = 0.5 and
  ease(t) + ease(1 − t) = 1; monotone on a sample grid.
- `progress(t, start, end)`: 0 before, 1 after, linear between.
- `partialPolylines(polylines, f0, f1)`: total length preserved at (0, 1); half the
  length at (0, 0.5); a cut that spans two polylines returns pieces from both, in order;
  (0, 0) returns `[]`; zero-length segments are skipped.
- `loadSplashSpec(path)`: loads `resources/brand/splash/splash-motion.json` and checks the
  keys the painter needs (`viewBox`, `timeline`, `strokeWidth`, `gradient`, `lowerHalves`,
  `dots`, `v`, `trace`, `tagline`, `background`); raises `ValueError` naming what is
  missing.
- `paintSplash(painter, spec, brandDir, t, target)`: one Qt test renders the frame at
  t = `timeline.end` into a 640×360 `QImage` and compares it with `varda-splash.svg`
  rendered by `QSvgRenderer` into another: mean absolute difference below a small
  threshold (antialiasing only), plus a t = 0 frame that is plain background. Geometry
  and timing come only from the JSON.

Conventions: camelCase in Qt-facing code, type hints without `Any`, no lazy imports.

## 3. Animated splash at startup

**Files:** `src/varda/branding/splash.py` (widget), `src/varda/main.py`,
`src/varda/branding/_tests/test_animated_splash.py`.

- `AnimatedSplash(QSplashScreen)`: owns a 640×360 logical `QPixmap` at the screen's
  `devicePixelRatio`; a ~60 fps `QTimer` repaints it with `paintSplash` at t from a
  `QElapsedTimer`; it stops the timer once t passes `timeline.end`.
- `finishWhenDone(window)`: if the animation has ended, or less than 1.0 s remains, it
  waits for the end then calls `finish(window)`; otherwise it jumps to the last frame and
  finishes at once. The main window never waits more than 1.0 s for the splash.
- `createSplash(app)`: returns `AnimatedSplash`, or a plain `QSplashScreen` showing
  `varda-splash.svg` rendered at HiDPI when `VARDA_STATIC_SPLASH=1` or the JSON fails to
  load. This also replaces today's `QPixmap(ICON_PATH)` splash.
- `main.initVarda()`: create the splash right after `QApplication`; call
  `q_app.processEvents()` after logging init, after `VardaApplication()` + plugins, after
  `MainGUI(...)`, and after `showMaximized()` (init blocks the timer otherwise); replace
  `splash.finish(app.maingui)` with `splash.finishWhenDone(app.maingui)`.
- Tests (pytest-qt, with a fake clock injected instead of `QElapsedTimer`): finishing with
  more than 1.0 s left closes immediately on the last frame; with less than 1.0 s left it
  closes when the animation ends; the env var and a broken JSON path both give the static
  splash.
- Manual check: `uv run varda` and `VARDA_STATIC_SPLASH=1 uv run varda`; time to main
  window within 1.0 s of before.

## 4. README header and CLAUDE.md

- Replace the opening `# Varda` with the spec's `<picture>` block (dark/light hero, 640
  wide). Nothing else in the README changes.
- CLAUDE.md, under Key Patterns: "Brand assets and rules: `resources/brand/README.md`. Use
  the files there as-is, and load static SVGs with QSvgRenderer, never the CSS-animated
  ones."

## Acceptance

- Icons regenerated (7-frame `.ico`, `.icns` to 1024); new V in the Dock and title bar.
- Animated splash runs and obeys the 1.0 s rule; `VARDA_STATIC_SPLASH=1` gives the
  static splash.
- `uv run pytest`, `ruff format`, `ruff check` and `ty check` clean for the touched files.
- `uv run pyinstaller Varda.spec` build launches with the new icon and splash.
- README header switches with the GitHub theme and animates once.

## Manual (Michael, on GitHub)

- Settings → General → Social preview: upload `docs/assets/varda-social-preview.png`.
