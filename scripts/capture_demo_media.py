"""Capture the README and website demo media from a real CRISM scene.

    uv run --extra hypyrameter python scripts/capture_demo_media.py \
        ~/Documents/Software/varda-demo-data/frt000047a3_07_if166j_mtr3.img docs/assets/demo

Drives a General Image Analysis workspace offscreen: a false-color view, ROIs
placed where HyPyRameter's olivine and clay parameters peak, their spectra, a
parameter overlay, a k-means classification and a short pixel-spectra clip.
Everything shown is computed from the scene; nothing is staged.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WINDOW = (1600, 1000)
SCALE = 2  # device pixel ratio of the captures, for sharp README images

# A headless screen big enough for the window, at 2x (the offscreen platform's
# default screen is 800x800); QT_SCALE_FACTOR makes it 2x
_SCREEN = Path(tempfile.gettempdir()) / "varda-demo-screen.json"
_SCREEN.write_text(
    json.dumps(
        {
            "screens": [
                {
                    "name": "demo",
                    "x": 0,
                    "y": 0,
                    "width": WINDOW[0] * SCALE,
                    "height": WINDOW[1] * SCALE,
                    "logicalDpi": 96,
                    "logicalBaseDpi": 96,
                }
            ]
        }
    )
)
os.environ["QT_QPA_PLATFORM"] = f"offscreen:configfile={_SCREEN}"
os.environ["QT_SCALE_FACTOR"] = str(SCALE)

import numpy as np  # noqa: E402
from PyQt6.QtCore import QPointF  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

from varda.analysis.band_parameters import BandParametersAnalysis  # noqa: E402
from varda.analysis.analysis import AnalysisContext  # noqa: E402
from varda.analysis.mapping import SamMappingAnalysis  # noqa: E402
from varda.common.di_types import ProjectImages  # noqa: E402
from varda.common.entities import Color, ROIMode, VardaRaster  # noqa: E402
from varda.common.palette import classColor  # noqa: E402
from varda.image_loading.image_loading_service import loadRaster  # noqa: E402
from varda.common.vec2 import Vec2  # noqa: E402
from varda.image_rendering.image_renderer import RenderMode  # noqa: E402
from varda.plotting.plot import RangeMode, VardaPlotWidget  # noqa: E402
from varda.workspaces.general_image_analysis import (  # noqa: E402
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)

FALSE_COLOR_NM = (2529.0, 1506.0, 1080.0)  # CRISM's FAL browse product
PARAMETERS = {"OLINDEX3": "olivine", "D2300": "Fe/Mg clay"}
ROI_HALF = 6  # pixels either side of each ROI's center
CLIP_POINTS = 6  # pixels clicked in the video clip
CLIP_FPS = 12
# olivine's 1 µm and the clays' 2.3 µm bands, before the thermal rise
PLOT_NM = (700.0, 2600.0)


def nearestBand(image: VardaRaster, nm: float) -> int:
    centers = np.asarray(image.bandModel.centers, dtype=float)
    return int(np.nanargmin(np.abs(centers - nm)))


def settle(app: QApplication, rounds: int = 5) -> None:
    for _ in range(rounds):
        app.processEvents()


def grab(widget: QWidget, path: Path) -> None:
    widget.grab().save(str(path))
    print("wrote", path)


def focusPlot(plot: VardaPlotWidget) -> None:
    """Show PLOT_NM with Y fitted to the spectra inside it (Manual range)."""
    lows, highs = [], []
    for curve in plot.plots:
        x, y = curve.plotDataItem.getData()
        if x is None or y is None:
            continue
        inside = (np.asarray(x) >= PLOT_NM[0]) & (np.asarray(x) <= PLOT_NM[1])
        values = np.asarray(y, dtype=float)[inside]
        values = values[np.isfinite(values)]
        if values.size:
            lows.append(values.min())
            highs.append(values.max())
    if not lows:
        return
    low, high = min(lows), max(highs)
    pad = 0.08 * (high - low)
    # the mode first: leaving Auto copies the current view into the range boxes
    plot.viewConfig.rangeMode.set(RangeMode.MANUAL)
    plot.rangeConfig.viewRangeX.set(Vec2(*PLOT_NM))
    plot.rangeConfig.viewRangeY.set(Vec2(low - pad, high + pad))


def runAnalysis(analysis, image: VardaRaster) -> VardaRaster:
    analysis.prepareFor(image)
    return analysis.run(image, lambda _percent, _message: None)


def peakCenter(values: np.ndarray, exclude: list[tuple[int, int]]) -> tuple[int, int]:
    """Center (col, row) of the window with the highest mean value inside the
    region the large view shows at first (the middle third of the scene), away
    from centers already chosen."""
    filled = np.full(values.shape, -np.inf)
    rows, cols = values.shape
    shown = (slice(rows // 3, 2 * rows // 3), slice(cols // 3, 2 * cols // 3))
    filled[shown] = np.where(np.isfinite(values[shown]), values[shown], -np.inf)
    best, where = -np.inf, (cols // 2, rows // 2)
    step = ROI_HALF
    for r in range(3 * step, rows - 3 * step, step):
        for c in range(3 * step, cols - 3 * step, step):
            if any(abs(c - x) < 6 * step and abs(r - y) < 6 * step for x, y in exclude):
                continue
            window = filled[r - step : r + step, c - step : c + step]
            score = float(np.mean(window))
            if score > best:
                best, where = score, (c, r)
    return where


def roiPolygon(image: VardaRaster, col: int, row: int) -> Polygon:
    corners = [
        (col - ROI_HALF, row - ROI_HALF),
        (col + ROI_HALF, row - ROI_HALF),
        (col + ROI_HALF, row + ROI_HALF),
        (col - ROI_HALF, row + ROI_HALF),
    ]
    return Polygon(image.imageToGeo(np.asarray(corners, dtype=float)))


def encodeClip(frames: Path, out: Path) -> None:
    """MP4 for the website and a small GIF for the README."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg not found; skipping the clip")
        return
    pattern = str(frames / "frame_%04d.png")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(CLIP_FPS),
            "-i",
            pattern,
            "-vf",
            "scale=1600:-2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "24",
            str(out / "varda-demo.mp4"),
        ],
        check=True,
    )
    palette = frames / "palette.png"
    scale = "fps=8,scale=900:-1:flags=lanczos"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            pattern,
            "-vf",
            f"{scale},palettegen=max_colors=128",
            str(palette),
        ],
        check=True,
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(CLIP_FPS),
            "-i",
            pattern,
            "-i",
            str(palette),
            "-lavfi",
            f"{scale}[x];[x][1:v]paletteuse=dither=bayer",
            str(out / "varda-demo.gif"),
        ],
        check=True,
    )
    print("wrote", out / "varda-demo.mp4", "and", out / "varda-demo.gif")


def main(cubePath: str, outDir: str) -> None:
    out = Path(outDir)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)

    image = loadRaster(cubePath)
    print("loaded", image.name, image.shape)
    images = ProjectImages([image])

    parameters = BandParametersAnalysis()
    parameters.prepareFor(image)
    parameters.parameters.set(list(PARAMETERS))
    parameterImage = parameters.run(image, lambda _p, _m: None)
    images.append(parameterImage)
    print("band parameters:", parameterImage.bandNames)

    config = GeneralImageAnalysisConfig(images)
    config.image.set(image)
    workspace = GeneralImageAnalysisWorkflow(config)
    workspace.resize(*WINDOW)
    workspace.show()
    # More room for the image and spectra than the default layout gives
    workspace.histogramDock.toggleView(False)
    workspace.settingsDock.toggleView(False)
    settle(app)

    settings = workspace.imageRenderer.settings
    with settings.sigParameterChanged.blocked():
        settings.mode.set(RenderMode.RGB)
        for param, nm in zip(
            (settings.rgb.red, settings.rgb.green, settings.rgb.blue), FALSE_COLOR_NM
        ):
            param.set(nearestBand(image, nm))
        settings.stretch.selectByName("Linear Percentile")
    settings.sigParameterChanged.emit(settings)
    settle(app)

    # ROIs where each parameter peaks, plus a typical patch for comparison
    chosen: list[tuple[int, int]] = []
    for band, (name, label) in enumerate(PARAMETERS.items()):
        values = np.asarray(parameterImage.getBands([band]), dtype=float)[:, :, 0]
        col, row = peakCenter(values, chosen)
        chosen.append((col, row))
        workspace.roiCollection.addROI(
            roiPolygon(image, col, row), label, _color(band), ROIMode.RECTANGLE
        )
    rows, cols = image.shape[:2]
    first = np.asarray(parameterImage.getBands([0]), dtype=float)[:, :, 0]
    typical = -np.abs(first - np.nanmedian(first))  # highest where most typical
    background = peakCenter(typical, chosen)
    chosen.append(background)
    workspace.roiCollection.addROI(
        roiPolygon(image, *background), "typical terrain", _color(2), ROIMode.RECTANGLE
    )
    for fid in workspace.roiCollection.fids:
        workspace.roiManagerWidget.plotSpectrum(fid)
    workspace.plotDock.setAsCurrentTab()
    settle(app)
    focusPlot(workspace.plotWidget)  # after the curves: plotting the first resets it
    settle(app)
    grab(workspace, out / "workspace-rois-spectra.png")

    # A band parameter laid over the scene
    workspace.overlayBar.setOverlay(parameterImage)
    workspace.overlayBar.layerBox.setCurrentText("OLINDEX3")
    workspace.overlayBar.opacitySlider.setValue(70)
    renderer = workspace.overlayBar.renderer
    if renderer is not None:  # spread the color map over the bulk of the values
        renderer.settings.stretch.selectByName("Linear Percentile")
    settle(app)
    grab(workspace, out / "parameter-overlay.png")

    # Spectral Angle Mapper with the ROI classes as endmembers, with its legend
    sam = SamMappingAnalysis()
    sam.setContext(AnalysisContext(rois=workspace.roiCollection))
    sam.prepareFor(image)
    sam.rois.selectAll()
    classes = sam.run(image, lambda _p, _m: None)
    images.append(classes)
    settle(app)
    workspace.overlayBar.setOverlay(classes)
    workspace.overlayBar.opacitySlider.setValue(60)
    settle(app)
    grab(workspace, out / "classification-overlay.png")
    workspace.overlayBar.setOverlay(None)
    settle(app)

    # Clip: clicking pixels adds their spectra and marks them on the image
    workspace.pixelPlotDock.setAsCurrentTab()
    settle(app)
    with tempfile.TemporaryDirectory() as folder:
        frames = Path(folder)
        index = 0
        rng = np.random.default_rng(3)
        targets = chosen[:2] + [
            (int(rng.integers(40, cols - 40)), int(rng.integers(40, rows - 40)))
            for _ in range(CLIP_POINTS - 2)
        ]
        for _ in range(CLIP_FPS):  # hold on the starting view
            grab(workspace, frames / f"frame_{index:04d}.png")
            index += 1
        for col, row in targets:
            workspace._onPixelSelected(image, QPointF(col, row))
            settle(app)
            focusPlot(workspace.pixelPlotWidget)
            settle(app)
            for _ in range(CLIP_FPS):  # one second per click
                workspace.grab().save(str(frames / f"frame_{index:04d}.png"))
                index += 1
        encodeClip(frames, out)
    workspace.close()


def _color(index: int) -> Color:
    return Color.fromHexString(classColor(index) + "80")  # half-transparent fill


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
