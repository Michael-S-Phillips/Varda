from dataclasses import dataclass


@dataclass(frozen=True)
class Stretch:
    """represents a stretch configuration."""

    name: str
    minR: int
    maxR: int
    minG: int
    maxG: int
    minB: int
    maxB: int
