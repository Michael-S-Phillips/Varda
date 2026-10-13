"""The Varda splash: a draw-on animation of the wordmark ("one pen,
branching"), painted with QPainter from resources/brand/splash/splash-motion.json
(schema 2: geometry, colors and timing all come from the JSON). Its last frame
matches varda-splash.svg, which is also the static fallback.

The animation runs while the app initializes and never holds the main window
back by more than a second: see ``AnimatedSplash.finishWhenDone``.
"""

from __future__ import annotations

import json
import math
import os
from bisect import bisect_right
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QCursor,
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QScreen,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QWidget

from varda.utilities.resources import resource_path

Point = tuple[float, float]

BRAND_DIR = Path(resource_path("resources/brand"))
SPLASH_SPEC_PATH = BRAND_DIR / "splash" / "splash-motion.json"
STATIC_SPLASH_PATH = BRAND_DIR / "splash" / "varda-splash.svg"
STATIC_SPLASH_ENV = "VARDA_STATIC_SPLASH"
LOGICAL_SIZE = (640, 360)
FRAME_MS = 16  # ~60 fps
# The splash never holds the window back longer than this: with more left
# when the window is ready, the rest of the animation plays faster
MAX_WAIT_SECONDS = 1.0

SCHEMA = 2
_REQUIRED_KEYS = (
    "viewBox",
    "background",
    "strokeWidth",
    "cut",
    "gradient",
    "lowerColor",
    "clipOut",
    "strokes",
    "dots",
    "tagline",
    "end",
)


# --- pure helpers ---------------------------------------------------------------


def loadSplashSpec(path: Path) -> dict:
    """The splash motion spec, checked for its schema and the keys the painter
    uses (a ValueError makes ``createSplash`` fall back to the static splash)."""
    spec = json.loads(Path(path).read_text())
    if spec.get("schema") != SCHEMA:
        raise ValueError(f"Splash spec {path} is not schema {SCHEMA}")
    missing = [key for key in _REQUIRED_KEYS if key not in spec]
    if missing:
        raise ValueError(f"Splash spec {path} is missing: {', '.join(missing)}")
    return spec


def cubicBezierEase(
    x1: float, y1: float, x2: float, y2: float
) -> Callable[[float], float]:
    """CSS cubic-bezier() timing function: time fraction -> progress."""

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
    """Fraction of the way from start to end at time t, clamped to [0, 1]."""
    return min(1.0, max(0.0, (t - start) / (end - start)))


def keyframeFraction(keys: list[list[float]], t: float) -> float:
    """Linear interpolation of (time, fraction) keyframes: 0 before the first,
    1 after the last."""
    if t <= keys[0][0]:
        return 0.0
    if t >= keys[-1][0]:
        return 1.0
    i = bisect_right([key[0] for key in keys], t)
    (t0, f0), (t1, f1) = keys[i - 1], keys[i]
    return f0 + (f1 - f0) * (t - t0) / (t1 - t0)


def partialPolyline(poly: list[Point], f: float) -> list[Point]:
    """The first fraction ``f`` of a polyline, by arc length."""
    target = f * sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))
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


def partialPolylines(
    polylines: list[list[Point]], f0: float, f1: float
) -> list[list[Point]]:
    """The stretch of a chain of polylines between arc-length fractions f0..f1."""
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
            if length == 0 or hi <= s0 or lo >= s1:  # touching the cut is not overlap
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


# --- painting ----------------------------------------------------------------------


def _toPath(poly: list[Point]) -> QPainterPath:
    path = QPainterPath(QPointF(*poly[0]))
    for x, y in poly[1:]:
        path.lineTo(x, y)
    return path


def _spectrumBrush(gradientSpec: dict) -> QBrush:
    gradient = QLinearGradient(gradientSpec["x1"], 0, gradientSpec["x2"], 0)
    for offset, color in gradientSpec["stops"]:
        gradient.setColorAt(offset, QColor(color))
    return QBrush(gradient)


_svgCache: dict[str, QSvgRenderer] = {}


def _svg(path: Path) -> QSvgRenderer:
    key = str(path)
    if key not in _svgCache:
        _svgCache[key] = QSvgRenderer(key)
    return _svgCache[key]


def _roundPen(brush: QBrush | QColor, width: float) -> QPen:
    return QPen(
        brush,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )


def paintSplash(
    p: QPainter, spec: dict, brandDir: Path, t: float, target: QRectF
) -> None:
    """Paint the splash at time t (seconds) into target (antialiasing on)."""
    x, y, w, h = spec["viewBox"]
    sw = spec["strokeWidth"]
    p.save()
    p.fillRect(target, QColor(spec["background"]))
    p.translate(target.topLeft())
    p.scale(target.width() / w, target.height() / h)
    p.translate(-x, -y)

    def drawStrokes(kind: str, pen: QPen) -> None:
        """Each stroke of ``kind``, drawn from its start as far as its
        keyframes say."""
        p.setPen(pen)
        for stroke in spec["strokes"]:
            if stroke["kind"] != kind:
                continue
            f = keyframeFraction(stroke["progress"], t)
            if f > 0:
                p.drawPath(_toPath(partialPolyline(stroke["polyline"], f)))

    # 1. the white lower halves, written in below the halfway line
    cut = spec["cut"]
    p.setClipRect(QRectF(x, cut, w, y + h - cut))
    drawStrokes("lower", _roundPen(QColor(spec["lowerColor"]), sw))
    p.setClipping(False)

    # 2. continuum dots pop in one after another (scale 0 -> 1.4 -> 1)
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
            scale, opacity = 1.4 * u / peak, 0.8 * u / peak
        else:
            fall = (u - peak) / (1 - peak)
            scale, opacity = 1.4 - 0.4 * fall, 0.8 - (0.8 - dots["opacity"]) * fall
        p.setOpacity(opacity)
        r = dots["radius"] * scale
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.setOpacity(1.0)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 3. the pen and its branches, clipped so round ends stop flat at the cut
    clip = QPainterPath()
    clip.addRect(QRectF(x, y, w, h))
    for rect in spec["clipOut"]:
        hole = QPainterPath()
        hole.addRect(QRectF(*rect))
        clip = clip.subtracted(hole)
    p.setClipPath(clip)
    drawStrokes("color", _roundPen(_spectrumBrush(spec["gradient"]), sw))
    p.setClipping(False)

    # 4. tagline fades in while rising into place
    tagline = spec["tagline"]
    u = cubicBezierEase(*tagline["easing"])(progress(t, *tagline["fadeIn"]))
    if u > 0:
        p.setOpacity(u)
        _svg(brandDir / "splash" / tagline["svg"]).render(
            p, QRectF(x, y + tagline["rise"] * (1 - u), w, h)
        )
    p.restore()


# --- the splash screen ---------------------------------------------------------------


def splashScreen() -> QScreen | None:
    """The display with the mouse on it, the one being looked at (as
    QSplashScreen chose); the primary display if that's unknown."""
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def _devicePixelRatio() -> float:
    screen = splashScreen()
    return screen.devicePixelRatio() if screen is not None else 1.0


def _blankPixmap() -> QPixmap:
    ratio = _devicePixelRatio()
    pixmap = QPixmap(round(LOGICAL_SIZE[0] * ratio), round(LOGICAL_SIZE[1] * ratio))
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def staticSplashPixmap() -> QPixmap:
    """varda-splash.svg rendered sharp at the screen's pixel ratio."""
    pixmap = _blankPixmap()
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _svg(STATIC_SPLASH_PATH).render(painter, QRectF(0, 0, *LOGICAL_SIZE))
    painter.end()
    return pixmap


class SplashWindow(QWidget):
    """A frameless, centered window showing a pixmap.

    Not QSplashScreen: its show() blocks for up to a second waiting for the
    window system, which on macOS is most of the time before anything
    appears."""

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._pixmap = pixmap
        # macOS hides splash (tool) windows while their app is in the
        # background, and an app launched from a terminal stays there until
        # its main window opens: without this the splash only flashed up then
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFixedSize(*LOGICAL_SIZE)
        screen = splashScreen()
        if screen is not None:
            self.setScreen(screen)
            frame = self.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            self.move(frame.topLeft())

    def pixmap(self) -> QPixmap:
        return self._pixmap

    def setPixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()

    def finish(self, window: QWidget) -> None:
        """Close now that ``window`` is up."""
        self.close()


class AnimatedSplash(SplashWindow):
    """Plays the draw-on while the app starts; see ``finishWhenDone``.

    ``clock`` returns seconds since the splash appeared (defaults to a
    QElapsedTimer; tests inject their own)."""

    def __init__(self, spec: dict, clock: Callable[[], float] | None = None) -> None:
        super().__init__(_blankPixmap())
        self.spec = spec
        self.end = float(spec["end"])
        if clock is None:
            elapsed = QElapsedTimer()
            elapsed.start()
            clock = lambda: elapsed.elapsed() / 1000.0  # noqa: E731
        self._clock = clock
        # (clock, animation time, speed) once the rest is sped up to fit
        self._speedUp: tuple[float, float, float] | None = None
        self._window: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._paintFrame()

    def currentTime(self) -> float:
        now = self._clock()
        if self._speedUp is None:
            return now
        since, start, speed = self._speedUp
        return start + (now - since) * speed

    def isDone(self) -> bool:
        return self.currentTime() >= self.end

    def _paintFrame(self) -> None:
        pixmap = self.pixmap()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paintSplash(
            painter,
            self.spec,
            BRAND_DIR,
            self.currentTime(),
            QRectF(0, 0, *LOGICAL_SIZE),
        )
        painter.end()
        self.setPixmap(pixmap)

    def _tick(self) -> None:
        self._paintFrame()
        if self.isDone():
            self._timer.stop()
            if self._window is not None:
                self.finish(self._window)

    def finishWhenDone(self, window: QWidget) -> None:
        """Close for ``window`` when the animation ends, within a second: if
        more is left, the rest plays faster rather than jumping to the end."""
        now = self.currentTime()
        remaining = self.end - now
        if remaining > MAX_WAIT_SECONDS:
            self._speedUp = (self._clock(), now, remaining / MAX_WAIT_SECONDS)
        if remaining <= 0:
            self._timer.stop()
            self._paintFrame()
            self.finish(window)
            return
        self._window = window  # _tick finishes when the animation ends


class StaticSplash(SplashWindow):
    """The final frame only (``VARDA_STATIC_SPLASH=1`` or no motion spec)."""

    def __init__(self) -> None:
        super().__init__(staticSplashPixmap())

    def finishWhenDone(self, window: QWidget) -> None:
        self.finish(window)


def createSplash(app: QApplication | None = None) -> AnimatedSplash | StaticSplash:
    """The animated splash, or the static one when ``VARDA_STATIC_SPLASH=1`` is
    set or the motion spec cannot be loaded."""
    if os.environ.get(STATIC_SPLASH_ENV) == "1":
        return StaticSplash()
    try:
        spec = loadSplashSpec(SPLASH_SPEC_PATH)
    except (OSError, ValueError):
        return StaticSplash()
    return AnimatedSplash(spec)
