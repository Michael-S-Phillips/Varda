from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from varda.app.project.roi_manager import ROIManager
from varda.core.entities import Image, Metadata, Stretch, Band


@dataclass
class Project:
    """
    Data representation of a Varda project.
    """

    path: Optional[Path] = None
    images: list[Image] = field(default_factory=list)
    roiManager: ROIManager = field(default_factory=ROIManager)

    # Does it make sense for roiManager to be here?

    @property
    def name(self) -> str:
        """Get the project name (derived from the filename)."""
        if self.path is None:
            return "Untitled Project"
        else:
            return self.path.name

    @property
    def directory(self) -> Path | None:
        """Get the directory containing the project file."""
        if self.path is None:
            return None
        return self.path.parent

    def serialize(self):
        """
        Serialize the project data into a JSON-compatible dictionary.

        Returns:
            dict: The serialized project data.
        """
        imageDictList = [
            {
                "metadata": image.metadata.serialize(),
                "stretch": [stretch.serialize() for stretch in image.stretch],
                "band": [band.serialize() for band in image.band],
            }
            for image in self.images
        ]

        # Serialize the ROI Manager
        roiManagerData = self.roiManager.serialize()

        return {
            "path": self.path,
            "images": imageDictList,
            "roiManager": roiManagerData,
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Project":
        """
        Populate the project from a serialized dictionary.

        Args:
            data (dict): The serialized project data.

        Returns:
            Project: The populated project instance.
        """
        path = Path(data["path"]) if data.get("path") else None
        images = []
        for i, imgData in enumerate(data.get("images", [])):
            metadata = Metadata.deserialize(imgData.get("metadata", {}))
            stretches = [Stretch.deserialize(s) for s in imgData.get("stretch", [])]
            bands = [Band.deserialize(b) for b in imgData.get("band", [])]

            # Create the image with raster=None
            # The raster data will be loaded separately by the ProjectLoader
            # This is a clean separation of concerns - the Project entity handles
            # the structure and metadata, while the application layer handles
            # loading the actual image data
            image = Image(
                raster=None,
                metadata=metadata,
                stretch=stretches,
                band=bands,
                index=i,
            )
            images.append(image)

        if "roiManager" in data:
            roiManager = ROIManager.deserialize(data["roiManager"])
        else:
            roiManager = ROIManager()

        return cls(path=path, images=images, roiManager=roiManager)
