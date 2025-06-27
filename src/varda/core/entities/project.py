from dataclasses import dataclass

from varda.core.entities import Image


@dataclass
class Project:
    """
    Data representation of a Varda project.
    """
    name: str
    images: list[Image]
