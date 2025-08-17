"""
Domain entity for spectral band configuration in Varda.

This module defines the Band class, which represents a configuration for
visualizing spectral bands in a hyperspectral image.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Band:
    """
    Data representation of a spectral band configuration.

    A band configuration specifies which spectral bands to use for
    the red, green, and blue channels when visualizing a hyperspectral image.
    """

    name: str
    r: int
    g: int
    b: int

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the band configuration into a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: The serialized band configuration.
        """
        return {
            "name": self.name,
            "r": self.r,
            "g": self.g,
            "b": self.b,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Band":
        """
        Create a Band instance from serialized data.

        Args:
            data: The serialized band configuration.

        Returns:
            Band: The deserialized Band instance.
        """
        return cls(
            name=data.get("name", ""),
            r=data.get("r", 0),
            g=data.get("g", 0),
            b=data.get("b", 0),
        )

    @classmethod
    def createDefault(cls) -> "Band":
        """
        Create a default band configuration.

        Returns:
            Band: A default band configuration.
        """
        return cls(
            name="Default",
            r=0,
            g=1,
            b=2,
        )

    def __eq__(self, other):
        """
        Check if two band configurations are equal.

        Args:
            other: The other band configuration to compare with.

        Returns:
            bool: True if the band configurations are equal, False otherwise.
        """
        if not isinstance(other, Band):
            return False
        return (
            self.name == other.name
            and self.r == other.r
            and self.g == other.g
            and self.b == other.b
        )
