# Splash Motion v2: "One Pen, Branching" — Design

**Date:** 2026-10-13
**Status:** Approved (design). Michael picked this motion from three options on the design canvas.
**Replaces:** the draw-on timing and the `splash-motion.json` schema in `2026-10-12-varda-brand-identity-design.md`. The static splash, the fallback and the "never hold the window back more than a second" rule stay as they are.

## Why

The current draw-on ends jerkily, for three reasons:

- After the r, the pen jumps back to the left side of the d.
- It then sits still for about half a second while it invisibly retraces the d's stem.
- The white lower halves pop in all at once.

The new motion keeps the same beginning: the V draws and the continuum dots pop. From there, the V's pen keeps going as one continuous line at a steady speed:

1. It goes over the a and up the r.
2. It goes into the d and straight down its right side into the band.
3. It goes up and over the last a.

Side strokes grow out of the line where the letters split: the a's left side, the d's left side and the d's ascender. The white lower halves are written in as each stroke reaches the halfway line. Nothing jumps or stalls.

## What is already in the repo

| File | Status |
|---|---|
| `docs/assets/varda-hero-on-dark.svg`, `-on-light.svg` | **Updated** to the new motion. They play once (about 3.9 s), then hold. With reduced motion they show the final frame. No code change needed. |
| `resources/brand/splash/splash-motion-v2.json` | **New**, schema 2, for the in-app splash. It plays at 0.8× the web timing and ends at 3.1 s, against 2.3 s before. |
| `resources/brand/splash/splash-motion.json` | Still schema 1, which `branding/splash.py` reads today. It is replaced in step 4 below. |
| `resources/brand/splash/varda-splash.svg`, `varda-splash-tagline.svg` | Unchanged. The new motion's last frame matches `varda-splash.svg`; checked with QPainter against QSvgRenderer, the only differences are antialiasing. |

## Schema 2

The JSON keeps `viewBox`, `logicalSize`, `background`, `strokeWidth`, `gradient`, `dots` and `tagline` from schema 1, and adds or changes the rest:

```text
schema      2
cut         y of the halfway line (white strokes are clipped to y >= cut)
lowerColor  color of the white lower halves
clipOut     [x, y, w, h] rects excluded when painting color strokes (keeps their round ends
            from dipping below the cut)
strokes     list of {id, kind: "color" | "lower", polyline: [[x, y], ...],
            progress: [[seconds, fraction], ...]}
dots        centers, radius, color, opacity, plus popStart / stagger / pop (seconds)
tagline     svg, fadeIn [start, end], rise, easing
end         seconds at which the last frame is reached
```

**Rules:**

- Each stroke draws from its first point along its polyline.
- Its `progress` keyframes give (time, fraction of length), linearly interpolated: 0 before the first keyframe and 1 after the last.
- Paint order:
  1. `lower` strokes, using `lowerColor` with round caps, clipped to y ≥ `cut`
  2. dots
  3. `color` strokes, using the gradient with round caps, painted with the `clipOut` rects excluded
  4. the tagline

There are 10 strokes:

- `pen`: the V through to the last a
- `a-left`, `d-left`, `d-ascender`: the branches
- `a-bowl`, `a-stem`, `d-bowl`, `d-stem`, `a2-bowl`, `a2-stem`: the white lower halves

## Changes to `src/varda/branding/splash.py`

1. **`loadSplashSpec`**:
   - Require `schema == 2` and these keys: `viewBox`, `background`, `strokeWidth`, `cut`, `gradient`, `lowerColor`, `clipOut`, `strokes`, `dots`, `tagline`, `end`.
   - A schema-1 file should raise `ValueError`, so `createSplash` falls back to the static splash as it already does.
2. **Pure helpers.** Add `keyframeFraction(keys, t)` and `partialPolyline(poly, f)`, which returns the first fraction of a polyline by arc length. Keep `progress` and `cubicBezierEase` for the dots and tagline. Remove `partialPolylines` if nothing else uses it.
3. **`paintSplash`.** Replace the lower-halves, V and trace sections with the generic stroke loop from the reference below. The dots and tagline sections barely change: the dot timing moves from `timeline.dots` into `dots` itself.
4. **`AnimatedSplash`**:
   - Read `self.end = float(spec["end"])`.
   - Then replace `splash-motion.json` with `splash-motion-v2.json`: rename it over the old file and delete v1.
5. **Tests:**
   - Update `branding/_tests/test_splash_motion.py`. `keyframeFraction` should return 0 before the first keyframe, 1 after the last, and interpolate linearly in between. `partialPolyline` should return half of an L-shaped polyline correctly. Test the schema check too.
   - Update `test_animated_splash.py` wherever it reads `timeline.end`.
   - Keep, or add, a test that the frame at `end` matches `varda-splash.svg` within antialiasing.

## Acceptance

- `uv run varda` shows the new motion: no jump after the r, no stall on the d, and the whites drawn in rather than popping in.
- `VARDA_STATIC_SPLASH=1` and a broken spec both fall back to the static splash.
- `uv run pytest src/varda/branding` passes, along with the usual `ruff` and `ty` checks.

## Reference painter (verified)

This rendered `splash-motion-v2.json` frame by frame with PyQt6 6.10. Its last frame matches `varda-splash.svg` rendered by QSvgRenderer, apart from antialiasing. Adapt it to the repo's conventions (camelCase, type hints, no `Any`).

```python
"""Reference QPainter renderer for splash-motion.json schema 2 ("one pen, branching")."""

import json
import math
from bisect import bisect_right
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtSvg import QSvgRenderer

Point = tuple[float, float]


def cubicBezierEase(x1: float, y1: float, x2: float, y2: float):
    def ease(t: float) -> float:
        if t <= 0.0:
            return 0.0
        if t >= 1.0:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(40):
            s = (lo + hi) / 2
            x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s**3
            lo, hi = (s, hi) if x < t else (lo, s)
        s = (lo + hi) / 2
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s**3
    return ease


def progress(t: float, start: float, end: float) -> float:
    return min(1.0, max(0.0, (t - start) / (end - start)))


def keyframeFraction(keys: list[list[float]], t: float) -> float:
    """Linear interpolation of (time, fraction) keyframes; 0 before the first, 1 after the last."""
    if t <= keys[0][0]:
        return 0.0
    if t >= keys[-1][0]:
        return 1.0
    i = bisect_right([k[0] for k in keys], t)
    (t0, f0), (t1, f1) = keys[i - 1], keys[i]
    return f0 + (f1 - f0) * (t - t0) / (t1 - t0)


def partialPolyline(poly: list[Point], f: float) -> list[Point]:
    """The first fraction f of a polyline, by arc length."""
    total = sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))
    target = f * total
    out = [poly[0]]
    walked = 0.0
    for a, b in zip(poly, poly[1:]):
        length = math.dist(a, b)
        if walked + length >= target:
            u = (target - walked) / length if length else 0.0
            out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
            return out
        out.append(b)
        walked += length
    return out


def toPath(poly):
    path = QPainterPath(QPointF(*poly[0]))
    for x, y in poly[1:]:
        path.lineTo(x, y)
    return path


def spectrumBrush(g):
    lg = QLinearGradient(g["x1"], 0, g["x2"], 0)
    for off, col in g["stops"]:
        lg.setColorAt(off, QColor(col))
    return QBrush(lg)


def paintSplash(p: QPainter, spec: dict, brandDir: Path, t: float, target: QRectF) -> None:
    x, y, w, h = spec["viewBox"]
    sw = spec["strokeWidth"]
    p.save()
    p.fillRect(target, QColor(spec["background"]))
    p.translate(target.topLeft())
    p.scale(target.width() / w, target.height() / h)
    p.translate(-x, -y)

    def drawStrokes(kind: str, pen: QPen) -> None:
        p.setPen(pen)
        for st in spec["strokes"]:
            if st["kind"] != kind:
                continue
            f = keyframeFraction(st["progress"], t)
            if f > 0:
                p.drawPath(toPath(partialPolyline(st["polyline"], f)))

    # 1. white lower halves, clipped to below the cut
    p.setClipRect(QRectF(x, spec["cut"], w, y + h - spec["cut"]))
    drawStrokes("lower", QPen(QColor(spec["lowerColor"]), sw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setClipping(False)
    # 2. dots
    dots = spec["dots"]
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(dots["color"]))
    peak = 0.56
    for i, (cx, cy) in enumerate(dots["centers"]):
        start = dots["popStart"] + i * dots["stagger"]
        u = progress(t, start, start + dots["pop"])
        if u <= 0:
            continue
        if u < peak:
            scale, op = 1.4 * u / peak, 0.8 * u / peak
        else:
            fall = (u - peak) / (1 - peak)
            scale, op = 1.4 - 0.4 * fall, 0.8 - (0.8 - dots["opacity"]) * fall
        p.setOpacity(op)
        p.drawEllipse(QPointF(cx, cy), dots["radius"] * scale, dots["radius"] * scale)
    p.setOpacity(1.0)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # 3. colored strokes, with the drip boxes cut out
    clip = QPainterPath()
    clip.addRect(QRectF(x, y, w, h))
    for rect in spec["clipOut"]:
        hole = QPainterPath()
        hole.addRect(QRectF(*rect))
        clip = clip.subtracted(hole)
    p.setClipPath(clip)
    drawStrokes("color", QPen(spectrumBrush(spec["gradient"]), sw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setClipping(False)
    # 4. tagline
    tg = spec["tagline"]
    u = cubicBezierEase(*tg["easing"])(progress(t, *tg["fadeIn"]))
    if u > 0:
        p.setOpacity(u)
        QSvgRenderer(str(brandDir / "splash" / tg["svg"])).render(p, QRectF(x, y + tg["rise"] * (1 - u), w, h))
    p.restore()
```
