"""
Dual Image Link Manager

Manages image linking logic, coordinate transformations, and synchronization
between paired images in dual view mode.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from PyQt6.QtCore import QObject, pyqtSignal

from .dual_image_types import DualImageConfig, ImagePair, LinkType
from varda.project import ProjectContext

logger = logging.getLogger(__name__)


class DualImageLinkManager(QObject):
    """
    Manages linking between images for dual view functionality.

    Handles:
    - Creating and managing image pairs
    - Coordinate transformations between linked images
    - Synchronization events between paired images
    """

    # Signals
    images_linked = pyqtSignal(int, int)  # primary_index, secondary_index
    images_unlinked = pyqtSignal(int, int)  # primary_index, secondary_index
    link_config_changed = pyqtSignal(int, int)  # primary_index, secondary_index
    navigation_sync_requested = pyqtSignal(int, object)  # target_index, transform_data
    roi_sync_requested = pyqtSignal(int, str)  # target_index, roi_id

    def __init__(self, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.proj = project_context
        self._image_pairs: Dict[str, ImagePair] = {}  # pair_key -> ImagePair
        self._image_to_pairs: Dict[int, List[str]] = {}  # image_index -> [pair_keys]

        # Connect to project signals
        self.proj.sigDataChanged.connect(self._on_project_data_changed)

    def create_link(
        self,
        primary_index: int,
        secondary_index: int,
        config: Optional[DualImageConfig] = None,
    ) -> bool:
        """
        Create a link between two images.

        Args:
            primary_index: Index of the primary image
            secondary_index: Index of the secondary image
            config: Configuration for the link (uses default if None)

        Returns:
            bool: True if link was created successfully
        """
        if primary_index == secondary_index:
            logger.warning("Cannot link image to itself")
            return False

        # Check if images exist
        if not self._validate_image_indices(primary_index, secondary_index):
            return False

        # Check if already linked
        if self.are_images_linked(primary_index, secondary_index):
            logger.warning(
                f"Images {primary_index} and {secondary_index} are already linked"
            )
            return False

        # Use default config if none provided
        if config is None:
            config = DualImageConfig()

        # Validate link type compatibility
        if not self._validate_link_compatibility(
            primary_index, secondary_index, config.link_type
        ):
            return False

        # Create the image pair
        try:
            image_pair = ImagePair(primary_index, secondary_index, config)
            pair_key = self._get_pair_key(primary_index, secondary_index)

            # Store the pair
            self._image_pairs[pair_key] = image_pair

            # Update image-to-pairs mapping
            self._add_to_image_mapping(primary_index, pair_key)
            self._add_to_image_mapping(secondary_index, pair_key)

            # Setup coordinate transformation if needed
            self._setup_coordinate_transform(image_pair)

            logger.info(
                f"Successfully linked images {primary_index} and {secondary_index}"
            )
            self.images_linked.emit(primary_index, secondary_index)
            return True

        except Exception as e:
            logger.error(
                f"Failed to create link between images {primary_index} and {secondary_index}: {e}"
            )
            return False

    def remove_link(self, primary_index: int, secondary_index: int) -> bool:
        """
        Remove the link between two images.

        Args:
            primary_index: Index of the first image
            secondary_index: Index of the second image

        Returns:
            bool: True if link was removed successfully
        """
        pair_key = self._get_pair_key(primary_index, secondary_index)

        if pair_key not in self._image_pairs:
            logger.warning(
                f"No link exists between images {primary_index} and {secondary_index}"
            )
            return False

        # Remove from mappings
        self._remove_from_image_mapping(primary_index, pair_key)
        self._remove_from_image_mapping(secondary_index, pair_key)

        # Remove the pair
        del self._image_pairs[pair_key]

        logger.info(
            f"Successfully unlinked images {primary_index} and {secondary_index}"
        )
        self.images_unlinked.emit(primary_index, secondary_index)
        return True

    def are_images_linked(self, index1: int, index2: int) -> bool:
        """Check if two images are linked"""
        pair_key = self._get_pair_key(index1, index2)
        return pair_key in self._image_pairs

    def get_linked_images(self, image_index: int) -> List[int]:
        """Get all images linked to the given image"""
        linked_images = []

        if image_index in self._image_to_pairs:
            for pair_key in self._image_to_pairs[image_index]:
                if pair_key in self._image_pairs:
                    pair = self._image_pairs[pair_key]
                    other_index = pair.get_other_index(image_index)
                    if other_index is not None:
                        linked_images.append(other_index)

        return linked_images

    def get_image_pair(self, index1: int, index2: int) -> Optional[ImagePair]:
        """Get the image pair for two linked images"""
        pair_key = self._get_pair_key(index1, index2)
        return self._image_pairs.get(pair_key)

    def update_link_config(
        self, primary_index: int, secondary_index: int, config: DualImageConfig
    ) -> bool:
        """Update the configuration for an existing link"""
        pair_key = self._get_pair_key(primary_index, secondary_index)

        if pair_key not in self._image_pairs:
            logger.warning(
                f"No link exists between images {primary_index} and {secondary_index}"
            )
            return False

        # Update the configuration
        self._image_pairs[pair_key].config = config

        # Recalculate transformations if link type changed
        self._setup_coordinate_transform(self._image_pairs[pair_key])

        self.link_config_changed.emit(primary_index, secondary_index)
        return True

    def transform_coordinates(
        self, from_index: int, to_index: int, x: float, y: float
    ) -> Optional[Tuple[float, float]]:
        """
        Transform coordinates from one image to another.

        Args:
            from_index: Source image index
            to_index: Target image index
            x, y: Coordinates in source image

        Returns:
            Transformed coordinates (x, y) or None if transformation fails
        """
        pair = self.get_image_pair(from_index, to_index)
        if not pair:
            return None

        if pair.config.link_type == LinkType.PIXEL_BASED:
            # For pixel-based linking, coordinates are 1:1
            if pair.pixel_offset:
                offset_x, offset_y = pair.pixel_offset
                return (x + offset_x, y + offset_y)
            return (x, y)

        elif pair.config.link_type == LinkType.GEOSPATIAL:
            # Use transformation matrix for geospatial linking
            if pair.transform_matrix is not None:
                # Apply transformation (implementation depends on specific transform type)
                # This is a placeholder for actual geospatial transformation
                logger.warning(
                    "Geospatial coordinate transformation not yet implemented"
                )
                return (x, y)

        return None

    def notify_navigation_change(self, source_index: int, transform_data: Any):
        """Notify linked images of navigation changes (pan/zoom)"""
        linked_images = self.get_linked_images(source_index)

        for target_index in linked_images:
            pair = self.get_image_pair(source_index, target_index)
            if pair and pair.config.sync_navigation:
                self.navigation_sync_requested.emit(target_index, transform_data)

    def notify_roi_change(self, source_index: int, roi_id: str):
        """Notify linked images of ROI changes"""
        linked_images = self.get_linked_images(source_index)

        for target_index in linked_images:
            pair = self.get_image_pair(source_index, target_index)
            if pair and pair.config.sync_rois:
                self.roi_sync_requested.emit(target_index, roi_id)

    def get_all_pairs(self) -> List[ImagePair]:
        """Get all active image pairs"""
        return list(self._image_pairs.values())

    def cleanup_invalid_pairs(self):
        """Remove pairs that reference non-existent images"""
        valid_image_indices = set(range(len(self.proj.getAllImages())))
        pairs_to_remove = []

        for pair_key, pair in self._image_pairs.items():
            if (
                pair.primary_index not in valid_image_indices
                or pair.secondary_index not in valid_image_indices
            ):
                pairs_to_remove.append(pair_key)

        for pair_key in pairs_to_remove:
            pair = self._image_pairs[pair_key]
            self.remove_link(pair.primary_index, pair.secondary_index)

    # Private helper methods

    def _get_pair_key(self, index1: int, index2: int) -> str:
        """Generate a consistent key for an image pair"""
        return f"{min(index1, index2)}_{max(index1, index2)}"

    def _add_to_image_mapping(self, image_index: int, pair_key: str):
        """Add pair key to image mapping"""
        if image_index not in self._image_to_pairs:
            self._image_to_pairs[image_index] = []
        self._image_to_pairs[image_index].append(pair_key)

    def _remove_from_image_mapping(self, image_index: int, pair_key: str):
        """Remove pair key from image mapping"""
        if image_index in self._image_to_pairs:
            self._image_to_pairs[image_index].remove(pair_key)
            if not self._image_to_pairs[image_index]:
                del self._image_to_pairs[image_index]

    def _validate_image_indices(self, index1: int, index2: int) -> bool:
        """Validate that image indices exist"""
        try:
            images = self.proj.getAllImages()
            return 0 <= index1 < len(images) and 0 <= index2 < len(images)
        except Exception as e:
            logger.error(f"Error validating image indices: {e}")
            return False

    def _validate_link_compatibility(
        self, index1: int, index2: int, link_type: LinkType
    ) -> bool:
        """Validate that two images can be linked with the specified type"""
        try:
            image1 = self.proj.getImage(index1)
            image2 = self.proj.getImage(index2)

            if link_type == LinkType.PIXEL_BASED:
                # For pixel-based linking, images should have same dimensions
                if image1.raster.shape[:2] != image2.raster.shape[:2]:
                    logger.warning(
                        f"Images {index1} and {index2} have different dimensions for pixel-based linking"
                    )
                    return True  # Allow anyway, user may know what they're doing

            elif link_type == LinkType.GEOSPATIAL:
                # For geospatial linking, both images should have geospatial metadata
                if not (
                    hasattr(image1.metadata, "crs") and hasattr(image2.metadata, "crs")
                ):
                    logger.warning(
                        f"Images {index1} and {index2} lack geospatial metadata"
                    )
                    return True  # Allow anyway, user may know what they're doing

            return True

        except Exception as e:
            logger.error(f"Error validating link compatibility: {e}")
            return False

    def _setup_coordinate_transform(self, image_pair: ImagePair):
        """Setup coordinate transformation for the image pair"""
        if image_pair.config.link_type == LinkType.PIXEL_BASED:
            # For pixel-based, usually no offset needed
            image_pair.pixel_offset = (0, 0)

        elif image_pair.config.link_type == LinkType.GEOSPATIAL:
            # For geospatial, would setup transformation matrix
            # This is a placeholder for actual geospatial transformation setup
            logger.info("Geospatial transformation setup not yet implemented")
            image_pair.transform_matrix = None

    def _on_project_data_changed(self, *args):
        """Handle project data changes"""
        # Clean up any pairs that reference deleted images
        self.cleanup_invalid_pairs()
