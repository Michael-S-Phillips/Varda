from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """Data container representing a Band configuration for an image."""

    name: str
    r: int
    g: int
    b: int

    def toList(self):
        """get object data as a list in the format: [r, g, b]"""
        return [self.r, self.g, self.b]

    @classmethod
    def createDefault(cls):
        """Get a new Band object with default parameters"""
        return Band("default", 0, 0, 0)
