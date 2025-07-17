import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Set
import uuid

from PyQt6.QtCore import pyqtSignal, QObject

from varda.core.entities.roi import ROI, ROICustomData

logger = logging.getLogger(__name__)


class ROIManager(QObject):
    """Manages regions of interest (ROIs) across all images"""

    sigROIUpdated = pyqtSignal(str)
    sigROIAdded = pyqtSignal(str)
    sigROIRemoved = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.rois: Dict[str, ROI] = {}  # Dictionary of ROI ID to ROI object
        # Map of image index to list of ROI IDs
        self.imageROIMap: Dict[int, List[str]] = {}
        # Map of ROI ID to set of image indices
        self.ROIImageMap: Dict[str, List[int]] = {}

        logger.info("ROI Manager initialized")

    def addROI(self, roi: ROI, imageIndices: Optional[List[int]] = None) -> str:
        """
        Add an ROI to the manager

        Args:
            roi: The ROI to add
            imageIndices: List of image indices to associate with this ROI

        Returns:
            The ID of the ROI
        """
        if not isinstance(roi, ROI):
            logger.error("Invalid ROI object provided")
            raise TypeError("Invalid ROI object provided")

        # Ensure ROI has an ID
        if not roi.id:
            roi.id = str(uuid.uuid4())

        # Add to global collection
        self.rois[roi.id] = roi

        # Associate with images
        if roi.sourceImageIndex != -1:
            self.associateROIWithImage(roi.id, roi.sourceImageIndex)
        if imageIndices:
            for idx in imageIndices:
                self.associateROIWithImage(roi.id, idx)

        logger.info(
            f"Added ROI {roi.id} to manager. assosiated with image: {roi.sourceImageIndex}."
        )
        self.sigROIAdded.emit(roi.id)
        return roi.id

    def removeROI(self, roiID: str) -> bool:
        """
        Remove an ROI from the manager

        Args:
            roiID: The ID of the ROI to remove

        Returns:
            True if the ROI was removed, False otherwise
        """
        if roiID not in self.rois:
            logger.warning(f"ROI {roiID} not found in manager")
            return False

        # Remove from all image associations
        imageIndices = list(self.ROIImageMap[roiID])
        for idx in imageIndices:  # Use list() to avoid modification during iteration
            self.dissociateROIFromImage(roiID, idx)

        # Remove from global collection
        del self.rois[roiID]

        logger.info(f"Removed ROI {roiID} from manager")
        self.sigROIRemoved.emit(roiID)
        return True

    def updateROI(self, roiID: str, **properties) -> bool:
        """
        Update ROI properties

        Args:
            roiID: The ID of the ROI to update
            **properties: The properties to update

        Returns:
            True if the ROI was updated, False otherwise
        """
        if roiID not in self.rois:
            logger.warning(f"ROI {roiID} not found in manager")
            return False

        roi = self.rois[roiID]
        roi.updateProperties(**properties)

        logger.info(f"Updated ROI {roiID} properties: {list(properties.keys())}")
        self.sigROIUpdated.emit(roi.id)
        return True

    def getROI(self, roiID: str) -> Optional[ROI]:
        """
        Get an ROI by ID

        Args:
            roiID: The ID of the ROI to get

        Returns:
            The ROI, or None if not found
        """
        return self.rois.get(roiID)

    def getAllROIs(self) -> Dict[str, ROI]:
        """
        Get all ROIs

        Returns:
            Dictionary of ROI ID to ROI object
        """
        return self.rois

    def getROIsForImage(self, imageIndex: int) -> List[ROI]:
        """
        Get all ROIs associated with an image

        Args:
            imageIndex: The image index

        Returns:
            List of ROIs associated with the image
        """
        roi_ids = self.imageROIMap.get(imageIndex, [])
        return [self.rois[roiID] for roiID in roi_ids if roiID in self.rois]

    def getImagesForROI(self, roiID: str) -> List[int]:
        """
        Get all images associated with an ROI

        Args:
            roiID: The ID of the ROI

        Returns:
            List of image indices associated with the ROI
        """
        return self.ROIImageMap.get(roiID, [])

    def associateROIWithImage(self, roiID: str, imageIndex: int) -> bool:
        """
        Associate an ROI with an image

        Args:
            roiID: The ID of the ROI
            imageIndex: The image index

        Returns:
            True if the association was created, False otherwise
        """
        if roiID not in self.rois:
            logger.warning(f"ROI {roiID} not found in manager")
            return False

        if roiID not in self.ROIImageMap.keys():
            # create a new entry for this ROI if it doesn't exist
            self.ROIImageMap[roiID] = []

        # Add image to ROI's list
        if imageIndex not in self.ROIImageMap[roiID]:
            self.ROIImageMap[roiID].append(imageIndex)

        # Add ROI to image's list
        if imageIndex not in self.imageROIMap:
            self.imageROIMap[imageIndex] = []

        if roiID not in self.imageROIMap[imageIndex]:
            self.imageROIMap[imageIndex].append(roiID)

        logger.info(f"Associated ROI {roiID} with image {imageIndex}")
        self.sigROIUpdated.emit(roiID)
        return True

    def dissociateROIFromImage(self, roiID: str, imageIndex: int) -> bool:
        """
        Dissociate an ROI from an image

        Args:
            roiID: The ID of the ROI
            imageIndex: The image index

        Returns:
            True if the association was removed, False otherwise
        """
        if roiID not in self.rois:
            logger.warning(f"ROI {roiID} not found in manager")
            return False

        # Remove image from ROI's list
        if imageIndex in self.ROIImageMap[roiID]:
            self.ROIImageMap[roiID].remove(imageIndex)

        # Remove ROI from image's list
        if imageIndex in self.imageROIMap and roiID in self.imageROIMap[imageIndex]:
            self.imageROIMap[imageIndex].remove(roiID)

        logger.info(f"Dissociated ROI {roiID} from image {imageIndex}")
        self.sigROIUpdated.emit(roiID)
        return True

    def serialize(self) -> Dict:
        """
        Convert the ROI manager to a serializable dictionary

        Returns:
            Dictionary representation of the ROI manager
        """
        # Serialize ROIs
        serialized_rois = {}
        for roiID, roi in self.rois.items():
            serialized_rois[roiID] = roi.serialize()

        return {
            "rois": serialized_rois,
            "image_roi_map": self.imageROIMap,
            "roi_image_map": self.ROIImageMap,
        }

    @classmethod
    def deserialize(cls, data: Dict) -> "ROIManager":
        """
        Create an ROI manager from a serialized dictionary

        Args:
            data: Dictionary representation of the ROI manager

        Returns:
            The deserialized ROI manager
        """
        manager = cls()

        # Deserialize ROIs
        for roi_id, roi_data in data.get("rois", {}).items():
            roi = ROI.deserialize(roi_data)
            manager.rois[roi_id] = roi

        # Deserialize image-ROI mapping
        manager.imageROIMap = data.get("image_roi_map", {})

        logger.info(f"Deserialized ROI manager with {len(manager.rois)} ROIs")
        return manager
