from dataclasses import dataclass


@dataclass(slots=True)
class Vec2:
    x: float
    y: float

    @staticmethod
    def zero():
        return Vec2(0.0, 0.0)
