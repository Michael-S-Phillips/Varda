"""Generate platform icon files (.ico, .icns) from resources/logo.svg.

Rasterizes the SVG with Qt, then assembles the multi-resolution icon containers
with Pillow. Run after changing the logo:

    uv run python scripts/generate_icons.py
"""

import io
import sys
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import QBuffer
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = PROJECT_ROOT / "resources" / "logo.svg"
ICO_PATH = PROJECT_ROOT / "resources" / "logo.ico"
ICNS_PATH = PROJECT_ROOT / "resources" / "logo.icns"

# Sizes embedded in each container. .ico tops out at 256; .icns goes to 1024.
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def render_svg(size: int) -> Image.Image:
    """Render the SVG to a transparent RGBA Pillow image of the given square size."""
    renderer = QSvgRenderer(str(SVG_PATH))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    image.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data().data())).convert("RGBA")


def main() -> None:
    if not SVG_PATH.exists():
        sys.exit(f"Source SVG not found: {SVG_PATH}")

    app = QApplication(sys.argv)  # noqa: F841 - required for Qt rendering

    largest = max(max(ICO_SIZES), max(ICNS_SIZES))
    base = render_svg(largest)

    base.save(ICO_PATH, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    print(f"Wrote {ICO_PATH.relative_to(PROJECT_ROOT)}")

    base.save(ICNS_PATH, format="ICNS")
    print(f"Wrote {ICNS_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
