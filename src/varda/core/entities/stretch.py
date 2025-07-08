from dataclasses import dataclass


@dataclass(frozen=True)
class Stretch:
    """Immutable data container representing a Stretch configuration for an image."""

    name: str
    minR: float
    maxR: float
    minG: float
    maxG: float
    minB: float
    maxB: float

    def toList(self):
        """get object data as a list in the format:
        [[minR, maxR], [minG, maxG], [minB, maxB]]
        """
        return [[self.minR, self.maxR], [self.minG, self.maxG], [self.minB, self.maxB]]

    def serialize(self):
        # flatten list
        vals = [item for sublist in self.toList() for item in sublist]
        return [self.name, *vals]

    @classmethod
    def deserialize(cls, data):
        return cls(
            name=data[0],
            minR=data[1],
            maxR=data[2],
            minG=data[3],
            maxG=data[4],
            minB=data[5],
            maxB=data[6],
        )

    @classmethod
    def createDefault(cls):
        """Get a new Stretch object with default parameters"""
        return Stretch("default", 0, 1, 0, 1, 0, 1)
