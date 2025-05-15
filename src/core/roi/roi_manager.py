# src/core/roi/roi_manager.py (new consolidated file)

from typing import List, Dict, Optional, Any, Set
import uuid
import numpy as np
import logging
from PyQt6.QtCore import QObject, pyqtSignal

from core.entities.freehandROI import FreehandROI

logger = logging.getLogger(__name__)


class ROITableColumn:
    """Defines a column in the ROI table"""
    
    def __init__(self, name, data_type, formula=None, visible=True, width=100):
        """
        Initialize a new ROI table column
        
        Args:
            name: Column name
            data_type: Type of data ('text', 'number', 'boolean', 'dropdown', 'color')
            formula: Optional calculation formula
            visible: Whether the column is visible
            width: Column width in pixels
        """
        self.name = name
        self.data_type = data_type
        self.formula = formula
        self.visible = visible
        self.width = width
        self.options = []  # For dropdown type
    
    def serialize(self):
        """Convert to a serializable dictionary"""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "formula": self.formula,
            "visible": self.visible,
            "width": self.width,
            "options": self.options
        }
    
    @classmethod
    def deserialize(cls, data):
        """Create a column from a serialized dictionary"""
        column = cls(
            name=data.get("name", ""),
            data_type=data.get("data_type", "text"),
            formula=data.get("formula"),
            visible=data.get("visible", True),
            width=data.get("width", 100)
        )
        column.options = data.get("options", [])
        return column

class ROIManager(QObject):
    """Unified manager for all ROI operations across the application."""
    
    # Signals
    roiAdded = pyqtSignal(str)       # Emitted when an ROI is added (passes ROI ID)
    roiRemoved = pyqtSignal(str)     # Emitted when an ROI is removed (passes ROI ID)
    roiUpdated = pyqtSignal(str)     # Emitted when an ROI is updated (passes ROI ID)
    roiVisibilityChanged = pyqtSignal(str, bool)  # Emits ROI ID and visibility status
    
    def __init__(self, project_context):
        super().__init__()
        self.proj = project_context
        self.rois: Dict[str, FreehandROI] = {}  # Dictionary of ROI ID to ROI object
        self.image_roi_map: Dict[int, List[str]] = {}  # Map of image index to list of ROI IDs
        
    def add_roi(self, roi: FreehandROI, image_indices: Optional[List[int]] = None) -> str:
        """Add an ROI and associate it with specified images."""
        if not isinstance(roi, FreehandROI):
            logger.warning(f"Invalid ROI type: {type(roi).__name__}")
            return None
            
        # Ensure ROI has an ID
        if not roi.id:
            roi.id = str(uuid.uuid4())
            
        # Add to global collection
        self.rois[roi.id] = roi
        
        # Associate with images
        if image_indices:
            for idx in image_indices:
                self.associate_roi_with_image(roi.id, idx)
                roi.add_image_index(idx)
        
        # Emit signal
        self.roiAdded.emit(roi.id)
        
        logger.info(f"Added ROI {roi.id} to manager")
        return roi.id
        
    def remove_roi(self, roi_id: str) -> bool:
        """
        Remove an ROI from the manager
        
        Args:
            roi_id: The ID of the ROI to remove
            
        Returns:
            True if the ROI was removed, False otherwise
        """
        if roi_id not in self.rois:
            logger.warning(f"ROI {roi_id} not found in manager")
            return False
            
        # Get the ROI to remove image associations
        roi = self.rois[roi_id]
        
        # Remove from all image associations
        for image_idx in list(roi.image_indices):  # Use list() to avoid modification during iteration
            self.dissociate_roi_from_image(roi_id, image_idx)
            
        # Remove from global collection
        del self.rois[roi_id]
        
        logger.info(f"Removed ROI {roi_id} from manager")
        return True
    
    def update_roi(self, roi_id: str, **properties) -> bool:
        """
        Update ROI properties
        
        Args:
            roi_id: The ID of the ROI to update
            **properties: The properties to update
            
        Returns:
            True if the ROI was updated, False otherwise
        """
        if roi_id not in self.rois:
            logger.warning(f"ROI {roi_id} not found in manager")
            return False
            
        roi = self.rois[roi_id]
        roi.update_properties(**properties)
        
        logger.info(f"Updated ROI {roi_id} properties: {list(properties.keys())}")
        return True
    
    def get_roi(self, roi_id: str) -> Optional[FreehandROI]:
        """
        Get an ROI by ID
        
        Args:
            roi_id: The ID of the ROI to get
            
        Returns:
            The ROI, or None if not found
        """
        return self.rois.get(roi_id)
    
    def get_all_rois(self) -> Dict[str, FreehandROI]:
        """
        Get all ROIs
        
        Returns:
            Dictionary of ROI ID to ROI object
        """
        return self.rois
    
    def get_rois_for_image(self, image_index: int) -> List[FreehandROI]:
        """
        Get all ROIs associated with an image
        
        Args:
            image_index: The image index
            
        Returns:
            List of ROIs associated with the image
        """
        roi_ids = self.image_roi_map.get(image_index, [])
        return [self.rois[roi_id] for roi_id in roi_ids if roi_id in self.rois]
    
    def associate_roi_with_image(self, roi_id: str, image_index: int) -> bool:
        """
        Associate an ROI with an image
        
        Args:
            roi_id: The ID of the ROI
            image_index: The image index
            
        Returns:
            True if the association was created, False otherwise
        """
        if roi_id not in self.rois:
            logger.warning(f"ROI {roi_id} not found in manager")
            return False
            
        # Add image to ROI's list
        roi = self.rois[roi_id]
        roi.add_image_index(image_index)
        
        # Add ROI to image's list
        if image_index not in self.image_roi_map:
            self.image_roi_map[image_index] = []
            
        if roi_id not in self.image_roi_map[image_index]:
            self.image_roi_map[image_index].append(roi_id)
            
        logger.info(f"Associated ROI {roi_id} with image {image_index}")
        return True
    
    def dissociate_roi_from_image(self, roi_id: str, image_index: int) -> bool:
        """
        Dissociate an ROI from an image
        
        Args:
            roi_id: The ID of the ROI
            image_index: The image index
            
        Returns:
            True if the association was removed, False otherwise
        """
        if roi_id not in self.rois:
            logger.warning(f"ROI {roi_id} not found in manager")
            return False
            
        # Remove image from ROI's list
        roi = self.rois[roi_id]
        roi.remove_image_index(image_index)
        
        # Remove ROI from image's list
        if image_index in self.image_roi_map and roi_id in self.image_roi_map[image_index]:
            self.image_roi_map[image_index].remove(roi_id)
            
        logger.info(f"Dissociated ROI {roi_id} from image {image_index}")
        return True
    
    def add_column(self, name: str, data_type: str, formula: Optional[str] = None) -> Optional[ROITableColumn]:
        """
        Add a new custom column to the ROI table
        
        Args:
            name: Column name
            data_type: Column data type
            formula: Optional calculation formula
            
        Returns:
            The created column, or None if an error occurred
        """
        # Check for name conflicts
        if any(col.name == name for col in self.columns):
            logger.warning(f"Column '{name}' already exists")
            return None
        
        column = ROITableColumn(name, data_type, formula)
        self.columns.append(column)
        
        # Initialize this column for all existing ROIs
        for roi in self.rois.values():
            roi.custom_data.values[name] = None
            
        logger.info(f"Added column '{name}' of type '{data_type}' to ROI table")
        return column
    
    def remove_column(self, name: str) -> bool:
        """
        Remove a custom column from the ROI table
        
        Args:
            name: Column name
            
        Returns:
            True if the column was removed, False otherwise
        """
        # Don't allow removing default columns
        if any(col.name == name for col in self.default_columns):
            logger.warning(f"Cannot remove default column '{name}'")
            return False
            
        # Find and remove the column
        found = False
        self.columns = [col for col in self.columns if col.name != name or (found := True) is False]
        
        if not found:
            logger.warning(f"Column '{name}' not found")
            return False
            
        # Remove this column's data from all ROIs
        for roi in self.rois.values():
            if name in roi.custom_data.values:
                del roi.custom_data.values[name]
                
        logger.info(f"Removed column '{name}' from ROI table")
        return True
    
    def update_column(self, name: str, **properties) -> bool:
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
                        
                logger.info(f"Updated column '{name}' properties: {list(properties.keys())}")
                return True
                
        logger.warning(f"Column '{name}' not found")
        return False
    
    def get_column(self, name: str) -> Optional[ROITableColumn]:
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
    
    def get_all_columns(self) -> List[ROITableColumn]:
        """
        Get all columns
        
        Returns:
            List of all columns
        """
        return self.columns
    
    def calculate_formula_columns(self) -> None:
        """Update all formula-based columns for all ROIs"""
        formula_columns = [col for col in self.columns if col.formula]
        
        for roi in self.rois.values():
            for col in formula_columns:
                try:
                    # Evaluate the formula for this ROI
                    result = self._evaluate_formula(col.formula, roi)
                    roi.custom_data.values[col.name] = result
                except Exception as e:
                    logger.error(f"Error calculating formula for {col.name}: {e}")
    
    def _evaluate_formula(self, formula: str, roi: FreehandROI) -> Any:
        """
        Evaluate a formula for an ROI
        
        Args:
            formula: The formula to evaluate
            roi: The ROI to evaluate the formula for
            
        Returns:
            The result of the formula
        """
        # This is a simplified formula evaluator
        # A real implementation would need a proper formula parser
        
        # Create a safe environment with ROI properties
        env = {
            "roi": roi,
            "name": roi.name,
            "points": len(roi.points),
            "color": roi.color,
            "num_images": len(roi.image_indices),
        }
        
        # Add custom data
        for key, value in roi.custom_data.values.items():
            if isinstance(key, str) and key.isidentifier():
                env[key] = value
                
        # Add numpy functions
        env.update({
            "np": np,
            "mean": np.mean,
            "sum": np.sum,
            "min": np.min,
            "max": np.max,
        })
        
        # Basic formula evaluation
        # Note: eval() is generally not safe for user input, but this is just a placeholder
        # A real implementation would use a proper expression parser
        try:
            result = eval(formula, {"__builtins__": {}}, env)
            return result
        except Exception as e:
            logger.error(f"Error evaluating formula '{formula}': {e}")
            return None
    
    def serialize(self) -> Dict:
        """
        Convert the ROI manager to a serializable dictionary
        
        Returns:
            Dictionary representation of the ROI manager
        """
        # Serialize ROIs
        serialized_rois = {}
        for roi_id, roi in self.rois.items():
            serialized_rois[roi_id] = roi.serialize()
            
        # Serialize columns
        serialized_columns = [col.serialize() for col in self.columns]
            
        return {
            "rois": serialized_rois,
            "image_roi_map": self.image_roi_map,
            "columns": serialized_columns
        }
    
    @classmethod
    def deserialize(cls, data: Dict, project_context) -> 'ROIManager':
        """
        Create an ROI manager from a serialized dictionary
        
        Args:
            data: Dictionary representation of the ROI manager
            project_context: The ProjectContext this manager belongs to
            
        Returns:
            The deserialized ROI manager
        """
        manager = cls(project_context)
        
        # Deserialize columns
        manager.columns = []
        for col_data in data.get("columns", []):
            manager.columns.append(ROITableColumn.deserialize(col_data))
            
        # Add default columns if they're missing
        for default_col in manager.default_columns:
            if not any(col.name == default_col.name for col in manager.columns):
                manager.columns.append(default_col)
        
        # Deserialize ROIs
        for roi_id, roi_data in data.get("rois", {}).items():
            roi = FreehandROI.deserialize(roi_data)
            manager.rois[roi_id] = roi
            
        # Deserialize image-ROI mapping
        manager.image_roi_map = data.get("image_roi_map", {})
        
        logger.info(f"Deserialized ROI manager with {len(manager.rois)} ROIs and {len(manager.columns)} columns")
        return manager