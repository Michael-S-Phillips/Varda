"""Write a flyover's frames (PNG files) as an animated WebP or GIF. No Qt."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

from PIL import Image

FORMATS = {"Animated WebP": ".webp", "GIF": ".gif", "PNG frames (folder)": ""}


def _frames(paths: Sequence[Path]) -> Iterator[Image.Image]:
    for path in paths:  # one at a time: a flyover's frames don't fit in memory
        with Image.open(path) as image:
            yield image.convert("RGB")


def writeAnimation(frames: Sequence[Path], target: Path, fps: float = 30) -> Path:
    """Frames (PNG files, in order) as an animated image; the suffix of
    ``target`` (.webp or .gif) picks the format. Loops forever."""
    if not frames:
        raise ValueError("No frames to write.")
    images = _frames(frames)
    first = next(images)
    duration = round(1000 / fps)
    if target.suffix.lower() == ".gif":
        first.save(
            target,
            save_all=True,
            append_images=images,
            duration=duration,
            loop=0,
            optimize=False,
        )
    elif target.suffix.lower() == ".webp":
        first.save(
            target,
            save_all=True,
            append_images=images,
            duration=duration,
            loop=0,
            quality=88,
            method=4,
        )
    else:
        raise ValueError(f"Can't write {target.suffix} animations; use .webp or .gif.")
    return target
