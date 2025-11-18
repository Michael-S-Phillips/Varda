from dataclasses import dataclass


# TODO: Delete. Keeping for now just to not break some stuff that will also be deleted soon.
@dataclass(frozen=True)
class Stretch:
    """data container representing a Stretch configuration for an image."""

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

    def clone(self):
        return Stretch(
            self.name, self.minR, self.maxR, self.minG, self.maxG, self.minB, self.maxB
        )

    def serialize(self):
        return [self.name, *self.toList()]

    @classmethod
    def deserialize(cls, data):
        return cls(
            name=data[0],
            minR=data[1][0],
            maxR=data[1][1],
            minG=data[2][0],
            maxG=data[2][1],
            minB=data[3][0],
            maxB=data[3][1],
        )

    @classmethod
    def createDefault(cls):
        """Get a new Stretch object with default parameters"""
        return Stretch("default", 0, 1, 0, 1, 0, 1)
