# standard library
from typing import Any, Dict
from dataclasses import dataclass, field

# third-party imports
import numpy as np


# local imports
from .band import Band


# pylint: disable=too-many-instance-attributes
@dataclass
class Metadata:
    """Data container representing the metadata of an image.

    This ensures that every image contains a standard base set of metadata,
    but allows for adding extra metadata items via _extraMetadata.

    Note that this data container is mutable, But do not directly modify its contents.
    use ProjectContext to edit it so that the program knows when it's changed.
    """

    filePath: str = ""
    driver: str = ""
    width: int = 0
    height: int = 0
    dtype: str = ""
    dataIgnore: float = 0
    bandCount: int = 0
    defaultBand: Band = field(default_factory=Band.createDefault)
    wavelengths: np.ndarray = field(default_factory=lambda: np.zeros(0))
    extraMetadata: Dict[str, str | int | float] = field(default_factory=dict)


    def serialize(self):
        """Generates a dictionary representation of the metadata."""
        return {
            "filePath": self.filePath,
            "driver": self.driver,
            "width": self.width,
            "height": self.height,
            "dtype": self.dtype,
            "dataIgnore": self.dataIgnore,
            "bandCount": self.bandCount,
            "defaultBand": self.defaultBand.serialize(),
            "wavelengths": self.wavelengths.tolist(),
            "extraMetadata": self.extraMetadata
        }

    @classmethod
    def deserialize(cls, data: Any):
        """Deserialize a dictionary representation of the metadata."""
        return cls(
            filePath=data["filePath"],
            driver=data["driver"],
            width=data["width"],
            height=data["height"],
            dtype=data["dtype"],
            dataIgnore=data["dataIgnore"],
            bandCount=data["bandCount"],
            defaultBand=Band.deserialize(data["defaultBand"]),
            wavelengths=np.array(data["wavelengths"]),
            extraMetadata=data["extraMetadata"]
        )

    # other methods
    def toFlatDict(self):
        """generate a flat dict containing all the metadata and extra metadata"""
        coreMetadata = {
            key: value for key, value in self.__dict__.items() if key != "extraMetadata"
        }
        return {**coreMetadata, **self.extraMetadata}

    # magic methods to add the ability to iterate through the items
    def __iter__(self):
        items = self.toFlatDict()
        for attr, value in items:
            yield attr, value

    def __repr__(self):
        allItems = self.toFlatDict()
        out = "Metadata:\n"
        for key, value in allItems.items():
            out += "    " + f"{key}: {value}" + "\n"
        return out

    def __getitem__(self, item):
        return self.toFlatDict().get(item)
