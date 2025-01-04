from dataclasses import dataclass


@dataclass(frozen=True)
class Stretch:
    """Data container representing a Stretch configuration for an image."""

    name: str
    minR: int
    maxR: int
    minG: int
    maxG: int
    minB: int
    maxB: int

    def toList(self):
        """get object data as a list in the format:
        [[minR, maxR], [minG, maxG], [minB, maxB]]
        """
        return [[self.minR, self.maxR], [self.minG, self.maxG], [self.minB, self.maxB]]

    @classmethod
    def createDefault(cls):
        """Get a new Stretch object with default parameters"""
        return Stretch("default", 0, 1, 0, 1, 0, 1)
