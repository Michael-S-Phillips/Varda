"""Splash animation helpers: easing, progress, partial polylines, spec loading
and the painter's final frame."""

import json
import math

import numpy as np
import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

from varda.branding.splash import (
    BRAND_DIR,
    SPLASH_SPEC_PATH,
    cubicBezierEase,
    loadSplashSpec,
    paintSplash,
    partialPolylines,
    progress,
)


def test_easing_endpoints_clamp_and_symmetry():
    ease = cubicBezierEase(0.65, 0.0, 0.35, 1.0)
    assert ease(0.0) == 0.0 and ease(1.0) == 1.0
    assert ease(-0.5) == 0.0 and ease(1.5) == 1.0
    assert ease(0.5) == pytest.approx(0.5, abs=1e-6)
    for t in (0.1, 0.25, 0.4):
        assert ease(t) + ease(1 - t) == pytest.approx(1.0, abs=1e-6)
    samples = [ease(t) for t in np.linspace(0, 1, 50)]
    assert all(b >= a for a, b in zip(samples, samples[1:]))


def test_progress_is_clamped_and_linear():
    assert progress(0.0, 1.0, 2.0) == 0.0
    assert progress(3.0, 1.0, 2.0) == 1.0
    assert progress(1.25, 1.0, 2.0) == pytest.approx(0.25)


def _length(polylines):
    return sum(math.dist(a, b) for poly in polylines for a, b in zip(poly, poly[1:]))


def test_partial_polylines_lengths_and_spanning_cuts():
    chain = [[(0.0, 0.0), (10.0, 0.0)], [(10.0, 5.0), (10.0, 15.0)]]  # 10 + 10 long
    assert _length(partialPolylines(chain, 0.0, 1.0)) == pytest.approx(20.0)
    half = partialPolylines(chain, 0.0, 0.5)
    assert _length(half) == pytest.approx(10.0) and len(half) == 1
    spanning = partialPolylines(chain, 0.25, 0.75)
    assert len(spanning) == 2
    assert spanning[0][0] == pytest.approx((5.0, 0.0))
    assert spanning[1][-1] == pytest.approx((10.0, 10.0))
    assert partialPolylines(chain, 0.0, 0.0) == []
    assert _length(
        partialPolylines([[(0.0, 0.0), (0.0, 0.0), (3.0, 4.0)]], 0.0, 1.0)
    ) == pytest.approx(5.0)


def test_load_splash_spec_checks_its_keys(tmp_path):
    spec = loadSplashSpec(SPLASH_SPEC_PATH)
    assert spec["timeline"]["end"] == pytest.approx(2.3)
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"viewBox": [0, 0, 1, 1]}))
    with pytest.raises(ValueError, match="timeline"):
        loadSplashSpec(broken)


def _render(paint) -> np.ndarray:
    image = QImage(640, 360, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint(painter)
    painter.end()
    ptr = image.constBits()
    assert ptr is not None
    ptr.setsize(image.sizeInBytes())
    return np.frombuffer(ptr, dtype=np.uint8).reshape(360, 640, 4).astype(float)


def test_final_frame_matches_the_static_splash(qapp):
    spec = loadSplashSpec(SPLASH_SPEC_PATH)
    target = QRectF(0, 0, 640, 360)
    animated = _render(
        lambda p: paintSplash(p, spec, BRAND_DIR, spec["timeline"]["end"] + 0.1, target)
    )
    static = _render(
        lambda p: QSvgRenderer(str(BRAND_DIR / "splash" / "varda-splash.svg")).render(
            p, target
        )
    )
    assert np.mean(np.abs(animated - static)) < 3.0  # antialiasing differences only


def test_first_frame_is_just_the_background(qapp):
    spec = loadSplashSpec(SPLASH_SPEC_PATH)
    frame = _render(
        lambda p: paintSplash(p, spec, BRAND_DIR, 0.0, QRectF(0, 0, 640, 360))
    )
    background = QColor(spec["background"])
    expected = np.array(
        [background.blue(), background.green(), background.red(), 255], dtype=float
    )
    assert np.abs(frame - expected).max() < 2.0
