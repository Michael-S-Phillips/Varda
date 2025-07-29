"""
Domain entity for image stretch configuration in Varda.

This module defines the Stretch class, which represents a configuration for
stretching the dynamic range of an image for visualization.
"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class Stretch:
    """
    Data representation of an image stretch configuration.
    
    A stretch configuration specifies the minimum and maximum values for
    each color channel (red, green, blue) when visualizing an image.
    """

    name: str
    minR: float
    maxR: float
    minG: float
    maxG: float
    minB: float
    maxB: float

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the stretch configuration into a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: The serialized stretch configuration.
        """
        return {
            "name": self.name,
            "minR": self.minR,
            "maxR": self.maxR,
            "minG": self.minG,
            "maxG": self.maxG,
            "minB": self.minB,
            "maxB": self.maxB,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Stretch":
        """
        Create a Stretch instance from serialized data.

        Args:
            data: The serialized stretch configuration.

        Returns:
            Stretch: The deserialized Stretch instance.
        """
        return cls(
            name=data.get("name", ""),
            minR=float(data.get("minR", 0.0)),
            maxR=float(data.get("maxR", 1.0)),
            minG=float(data.get("minG", 0.0)),
            maxG=float(data.get("maxG", 1.0)),
            minB=float(data.get("minB", 0.0)),
            maxB=float(data.get("maxB", 1.0)),
        )

    @classmethod
    def createDefault(cls) -> "Stretch":
        """
        Create a default stretch configuration.

        Returns:
            Stretch: A default stretch configuration.
        """
        return cls(
            name="Default",
            minR=0.0,
            maxR=1.0,
            minG=0.0,
            maxG=1.0,
            minB=0.0,
            maxB=1.0,
        )

    def toList(self) -> List[float]:
        """
        Convert the stretch configuration to a list of min/max values.

        Returns:
            List[float]: A list of [minR, maxR, minG, maxG, minB, maxB].
        """
        return [self.minR, self.maxR, self.minG, self.maxG, self.minB, self.maxB]

    def __eq__(self, other):
        """
        Check if two stretch configurations are equal.

        Args:
            other: The other stretch configuration to compare with.

        Returns:
            bool: True if the stretch configurations are equal, False otherwise.
        """
        if not isinstance(other, Stretch):
            return False
        return (
            self.name == other.name
            and self.minR == other.minR
            and self.maxR == other.maxR
            and self.minG == other.minG
            and self.maxG == other.maxG
            and self.minB == other.minB
            and self.maxB == other.maxB
        )