from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """Immutable data container representing a Band configuration for an image."""

    name: str
    r: int
    g: int
    b: int

    def toList(self):
        """get object data as a list in the format: [r, g, b]"""
        return [self.r, self.g, self.b]

    def serialize(self):
        return [self.name, *self.toList()]

    @classmethod
    def deserialize(cls, data):
        return cls(*data)

    @classmethod
    def createDefault(cls):
        """Get a new Band object with default parameters"""
        return Band("default", 0, 0, 0)
