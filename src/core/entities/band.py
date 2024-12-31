from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """represents a band configuration."""

    name: str
    r: int
    g: int
    b: int
