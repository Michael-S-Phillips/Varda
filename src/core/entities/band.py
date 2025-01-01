from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """represents a band configuration."""

    name: str
    r: int
    g: int
    b: int

    @classmethod
    def createDefault(cls):
        return Band("default", 0, 0, 0)
