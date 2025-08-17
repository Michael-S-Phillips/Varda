"""
Domain entity for a Varda project.

This module defines the Project class, which represents a Varda project.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

from varda.common.domain.image import Image
from varda.common.domain.roi import ROI


@dataclass
class Project:
    """
    Data representation of a Varda project.

    A project contains a collection of images and ROIs, as well as metadata
    about the project itself.
    """

    path: Optional[Path] = None
    images: List[Image] = field(default_factory=list)
    rois: List[ROI] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Get the project name (derived from the filename)."""
        if self.path is None:
            return "Untitled Project"
        else:
            return self.path.name

    @property
    def directory(self) -> Optional[Path]:
        """Get the directory containing the project file."""
        if self.path is None:
            return None
        return self.path.parent

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the project data into a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: The serialized project data.
        """
        image_dict_list = [
            {
                "metadata": image.metadata.serialize(),
                "stretch": [stretch.serialize() for stretch in image.stretch],
                "band": [band.serialize() for band in image.band],
            }
            for image in self.images
        ]

        roi_dict_list = [roi.serialize() for roi in self.rois]

        return {
            "path": str(self.path) if self.path else None,
            "images": image_dict_list,
            "rois": roi_dict_list,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Project":
        """
        Create a Project instance from serialized data.

        Args:
            data: The serialized project data.

        Returns:
            Project: The deserialized Project instance.
        """
        from varda.common.domain.metadata import Metadata
        from varda.common.domain.band import Band
        from varda.common.domain.stretch import Stretch

        project = cls()
        project.path = Path(data["path"]) if data.get("path") else None

        # Deserialize images
        project.images = []
        for i, img_data in enumerate(data.get("images", [])):
            metadata = Metadata.deserialize(img_data.get("metadata", {}))
            stretches = [Stretch.deserialize(s) for s in img_data.get("stretch", [])]
            bands = [Band.deserialize(b) for b in img_data.get("band", [])]

            # Create the image with raster=None
            # The raster data will be loaded separately by the ProjectLoader
            image = Image(
                raster=None,
                metadata=metadata,
                stretch=stretches,
                band=bands,
                index=i,
            )
            project.images.append(image)

        # Deserialize ROIs
        project.rois = [ROI.deserialize(r) for r in data.get("rois", [])]

        return project
