import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Set
import uuid

from varda.core.entities.roi import ROI, ROICustomData

logger = logging.getLogger(__name__)


class ROITableColumn:
    """Defines a column in the ROI table"""

    def __init__(self, name, dataType, formula=None, visible=True, width=100):
        """
        Initialize a new ROI table column

        Args:
            name: Column name
            dataType: Type of data ('text', 'number', 'boolean', 'dropdown', 'color')
            formula: Optional calculation formula
            visible: Whether the column is visible
            width: Column width in pixels
        """
        self.name = name
        self.dataType = dataType
        self.formula = formula
        self.visible = visible
        self.width = width
        self.options = []  # For dropdown type

    def serialize(self):
        """Convert to a serializable dictionary"""
        return {
            "name": self.name,
            "data_type": self.dataType,
            "formula": self.formula,
            "visible": self.visible,
            "width": self.width,
            "options": self.options,
        }

    @classmethod
    def deserialize(cls, data):
        """Create a column from a serialized dictionary"""
        column = cls(
            name=data.get("name", ""),
            dataType=data.get("data_type", "text"),
            formula=data.get("formula"),
            visible=data.get("visible", True),
            width=data.get("width", 100),
        )
        column.options = data.get("options", [])
        return column


class ROIManager:
    """Manages regions of interest (ROIs) across all images"""

    def __init__(self):
        self.rois: Dict[str, ROI] = {}  # Dictionary of ROI ID to ROI object
        self.imageROIMap: Dict[int, List[str]] = (
            {}
        )  # Map of image index to list of ROI IDs
        self.ROIImageMap: Dict[str, List[int]] = (
            {}
        )  # Map of ROI ID to set of image indices

        # Initialize columns
        self.columns: List[ROITableColumn] = []
        self.defaultColumns = [
            ROITableColumn("ID", "text", visible=True),
            ROITableColumn("Name", "text", visible=True),
            ROITableColumn("Color", "color", visible=True),
            ROITableColumn("Images", "text", visible=True),
            ROITableColumn("Points", "number", visible=True),
            ROITableColumn("Description", "text", visible=True),
        ]
        self.columns.extend(self.defaultColumns)

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
        if imageIndices:
            for idx in imageIndices:
                self.associateROIWithImage(roi.id, idx)

        logger.info(f"Added ROI {roi.id} to manager")
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
        roi.update_properties(**properties)

        logger.info(f"Updated ROI {roiID} properties: {list(properties.keys())}")
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

        # Add image to ROI's list
        if imageIndex not in self.ROIImageMap[roiID]:
            self.ROIImageMap[roiID].append(imageIndex)

        # Add ROI to image's list
        if imageIndex not in self.imageROIMap:
            self.imageROIMap[imageIndex] = []

        if roiID not in self.imageROIMap[imageIndex]:
            self.imageROIMap[imageIndex].append(roiID)

        logger.info(f"Associated ROI {roiID} with image {imageIndex}")
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
        return True

    def addColumn(
        self, name: str, dataType: str, formula: Optional[str] = None
    ) -> Optional[ROITableColumn]:
        """
        Add a new custom column to the ROI table

        Args:
            name: Column name
            dataType: Column data type
            formula: Optional calculation formula

        Returns:
            The created column, or None if an error occurred
        """
        # Check for name conflicts
        if any(col.name == name for col in self.columns):
            logger.warning(f"Column '{name}' already exists")
            return None

        column = ROITableColumn(name, dataType, formula)
        self.columns.append(column)

        # Initialize this column for all existing ROIs
        for roi in self.rois.values():
            roi.customData.values[name] = None

        logger.info(f"Added column '{name}' of type '{dataType}' to ROI table")
        return column

    def removeColumn(self, name: str) -> bool:
        """
        Remove a custom column from the ROI table

        Args:
            name: Column name

        Returns:
            True if the column was removed, False otherwise
        """
        # Don't allow removing default columns
        if any(col.name == name for col in self.defaultColumns):
            logger.warning(f"Cannot remove default column '{name}'")
            return False

        # Find and remove the column
        found = False
        self.columns = [
            col for col in self.columns if col.name != name or (found := True) is False
        ]

        if not found:
            logger.warning(f"Column '{name}' not found")
            return False

        # Remove this column's data from all ROIs
        for roi in self.rois.values():
            if name in roi.customData.values:
                del roi.customData.values[name]

        logger.info(f"Removed column '{name}' from ROI table")
        return True

    def updateColumn(self, name: str, **properties) -> bool:
        """
        Update a column's properties

        Args:
            name: Column name
            **properties: Properties to update

        Returns:
            True if the column was updated, False otherwise
        """
        for column in self.columns:
            if column.name == name:
                for key, value in properties.items():
                    if hasattr(column, key):
                        setattr(column, key, value)

                logger.info(
                    f"Updated column '{name}' properties: {list(properties.keys())}"
                )
                return True

        logger.warning(f"Column '{name}' not found")
        return False

    def getColumn(self, name: str) -> Optional[ROITableColumn]:
        """
        Get a column by name

        Args:
            name: Column name

        Returns:
            The column, or None if not found
        """
        for column in self.columns:
            if column.name == name:
                return column

        return None

    def getAllColumns(self) -> List[ROITableColumn]:
        """
        Get all columns

        Returns:
            List of all columns
        """
        return self.columns

    def calculateFormulaColumns(self) -> None:
        """Update all formula-based columns for all ROIs"""
        formulaColumns = [col for col in self.columns if col.formula]

        for roi in self.rois.values():
            for col in formulaColumns:
                try:
                    # Evaluate the formula for this ROI
                    result = self._evaluateFormula(col.formula, roi)
                    roi.customData.values[col.name] = result
                except Exception as e:
                    logger.error(f"Error calculating formula for {col.name}: {e}")

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

        # Serialize columns
        serializedColumns = [col.serialize() for col in self.columns]

        return {
            "rois": serialized_rois,
            "image_roi_map": self.imageROIMap,
            "columns": serializedColumns,
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

        # Deserialize columns
        manager.columns = []
        for col_data in data.get("columns", []):
            manager.columns.append(ROITableColumn.deserialize(col_data))

        # Add default columns if they're missing
        for default_col in manager.defaultColumns:
            if not any(col.name == default_col.name for col in manager.columns):
                manager.columns.append(default_col)

        # Deserialize ROIs
        for roi_id, roi_data in data.get("rois", {}).items():
            roi = ROI.deserialize(roi_data)
            manager.rois[roi_id] = roi

        # Deserialize image-ROI mapping
        manager.imageROIMap = data.get("image_roi_map", {})

        logger.info(
            f"Deserialized ROI manager with {len(manager.rois)} ROIs and {len(manager.columns)} columns"
        )
        return manager
