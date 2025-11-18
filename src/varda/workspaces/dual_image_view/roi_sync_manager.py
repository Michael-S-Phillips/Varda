"""
ROI Synchronization Manager

Handles synchronization of ROIs between linked images in dual view mode.
"""

import logging
from typing import Dict, Optional, Set
from PyQt6.QtCore import QObject, pyqtSignal

from varda.project import ProjectContext
from varda.common.entities import ROI

logger = logging.getLogger(__name__)


class ROISyncManager(QObject):
    """
    Manages ROI synchronization between linked images.

    Handles:
    - Copying ROIs between linked images
    - Coordinate transformation for ROIs
    - Maintaining sync state to prevent infinite loops
    - ROI visibility synchronization
    """

    # Signals
    roi_sync_completed = pyqtSignal(str, int, int)  # roi_id, source_index, target_index
    roi_sync_failed = pyqtSignal(
        str, int, int, str
    )  # roi_id, source_index, target_index, error

    def __init__(self, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.proj = project_context

        # Track which ROIs are currently being synced to prevent infinite loops
        self._syncing_rois: Set[str] = set()

        # Track ROI mappings between images: {(primary_idx, secondary_idx): {roi_id: synced_roi_id}}
        self._roi_mappings: Dict[tuple, Dict[str, str]] = {}

    def setup_roi_sync(self, primary_index: int, secondary_index: int):
        """
        Set up ROI synchronization between two images.

        Args:
            primary_index: Index of the primary image
            secondary_index: Index of the secondary image
        """
        pair_key = self._get_pair_key(primary_index, secondary_index)

        if pair_key not in self._roi_mappings:
            self._roi_mappings[pair_key] = {}

        # Sync existing ROIs from primary to secondary
        self._sync_existing_rois(primary_index, secondary_index)

        logger.debug(
            f"ROI sync set up for images {primary_index} <-> {secondary_index}"
        )

    def cleanup_roi_sync(self, primary_index: int, secondary_index: int):
        """
        Clean up ROI synchronization between two images.

        Args:
            primary_index: Index of the primary image
            secondary_index: Index of the secondary image
        """
        pair_key = self._get_pair_key(primary_index, secondary_index)

        if pair_key in self._roi_mappings:
            # Optionally remove synced ROIs from secondary image
            self._remove_synced_rois(primary_index, secondary_index)
            del self._roi_mappings[pair_key]

        logger.debug(
            f"ROI sync cleaned up for images {primary_index} <-> {secondary_index}"
        )

    def sync_roi(self, roi_id: str, source_index: int, target_index: int) -> bool:
        """
        Synchronize a specific ROI from source to target image.

        Args:
            roi_id: ID of the ROI to synchronize
            source_index: Index of the source image
            target_index: Index of the target image

        Returns:
            bool: True if sync was successful
        """
        # Prevent infinite sync loops
        if roi_id in self._syncing_rois:
            return True

        self._syncing_rois.add(roi_id)

        try:
            # Get the source ROI
            source_roi = self._get_roi_by_id(roi_id)
            if not source_roi:
                logger.warning(f"Source ROI {roi_id} not found in image {source_index}")
                return False

            # Transform ROI coordinates if needed
            transformed_roi = self._transform_roi_coordinates(
                source_roi, source_index, target_index
            )
            if not transformed_roi:
                logger.warning(f"Failed to transform ROI {roi_id} coordinates")
                return False

            # Create or update the synced ROI in target image
            synced_roi_id = self._create_or_update_synced_roi(
                transformed_roi, source_index, target_index, roi_id
            )

            if synced_roi_id:
                # Update mapping
                pair_key = self._get_pair_key(source_index, target_index)
                if pair_key not in self._roi_mappings:
                    self._roi_mappings[pair_key] = {}
                self._roi_mappings[pair_key][roi_id] = synced_roi_id

                self.roi_sync_completed.emit(roi_id, source_index, target_index)
                logger.debug(
                    f"Successfully synced ROI {roi_id} from {source_index} to {target_index}"
                )
                return True
            else:
                error_msg = (
                    f"Failed to create synced ROI in target image {target_index}"
                )
                self.roi_sync_failed.emit(roi_id, source_index, target_index, error_msg)
                return False

        except Exception as e:
            error_msg = f"Error syncing ROI {roi_id}: {str(e)}"
            logger.error(error_msg)
            self.roi_sync_failed.emit(roi_id, source_index, target_index, error_msg)
            return False

        finally:
            self._syncing_rois.discard(roi_id)

    def remove_synced_roi(
        self, roi_id: str, source_index: int, target_index: int
    ) -> bool:
        """
        Remove a synced ROI from the target image.

        Args:
            roi_id: ID of the source ROI
            source_index: Index of the source image
            target_index: Index of the target image

        Returns:
            bool: True if removal was successful
        """
        pair_key = self._get_pair_key(source_index, target_index)

        if pair_key in self._roi_mappings and roi_id in self._roi_mappings[pair_key]:
            synced_roi_id = self._roi_mappings[pair_key][roi_id]

            try:
                # Remove the synced ROI from target image
                if hasattr(self.proj, "roi_manager"):
                    success = self.proj.roiManager.removeROI(
                        target_index, synced_roi_id
                    )
                else:
                    # Fallback to legacy ROI removal
                    success = self._remove_roi_legacy(target_index, synced_roi_id)

                if success:
                    del self._roi_mappings[pair_key][roi_id]
                    logger.debug(
                        f"Removed synced ROI {synced_roi_id} from image {target_index}"
                    )
                    return True

            except Exception as e:
                logger.error(f"Error removing synced ROI {synced_roi_id}: {e}")

        return False

    def get_synced_roi_id(
        self, source_roi_id: str, source_index: int, target_index: int
    ) -> Optional[str]:
        """Get the synced ROI ID in the target image"""
        pair_key = self._get_pair_key(source_index, target_index)

        if pair_key in self._roi_mappings:
            return self._roi_mappings[pair_key].get(source_roi_id)

        return None

    # Private methods

    def _get_pair_key(self, index1: int, index2: int) -> tuple:
        """Generate a consistent key for an image pair"""
        return (min(index1, index2), max(index1, index2))

    def _sync_existing_rois(self, primary_index: int, secondary_index: int):
        """Sync all existing ROIs from primary to secondary image"""
        try:
            # Get existing ROIs from primary image
            primary_rois = self.proj.roiManager.getROIsForImage(primary_index)

            # Sync each ROI
            for roi in primary_rois:
                if hasattr(roi, "id"):
                    self.sync_roi(roi.id, primary_index, secondary_index)

        except Exception as e:
            logger.error(f"Error syncing existing ROIs: {e}")

    def _get_roi_by_id(self, roi_id: str):
        """Get an ROI by ID"""
        try:
            return self.proj.roiManager.getROI(roi_id)
        except Exception as e:
            logger.error(f"Error getting ROI {roi_id}: {e}")

        return None

    def _transform_roi_coordinates(self, roi, source_index: int, target_index: int):
        """Transform ROI coordinates from source to target image coordinate system"""
        try:
            # For now, assume pixel-based linking (1:1 coordinate mapping)
            # In the future, this would use the coordinate transformation from the link manager

            # Create a copy of the ROI with potentially transformed coordinates
            transformed_roi = self._copy_roi(roi)

            # For pixel-based linking, coordinates usually don't need transformation
            # For geospatial linking, we would apply coordinate transformations here

            return transformed_roi

        except Exception as e:
            logger.error(f"Error transforming ROI coordinates: {e}")
            return None

    def _copy_roi(self, roi):
        """Create a copy of an ROI"""
        try:
            if isinstance(roi, ROI):
                # Create a new FreehandROI with copied properties
                new_roi = ROI()

                # Copy basic properties
                if hasattr(roi, "points") and roi.points is not None:
                    new_roi.points = (
                        roi.points.copy() if hasattr(roi.points, "copy") else roi.points
                    )

                if hasattr(roi, "color"):
                    new_roi.color = roi.color

                if hasattr(roi, "name"):
                    new_roi.name = f"Synced_{roi.name}" if roi.name else "Synced_ROI"

                return new_roi
            else:
                # Generic ROI copy - this would need to be expanded for other ROI types
                logger.warning(f"Unknown ROI type for copying: {type(roi)}")
                return roi

        except Exception as e:
            logger.error(f"Error copying ROI: {e}")
            return None

    def _create_or_update_synced_roi(
        self, roi, source_index: int, target_index: int, source_roi_id: str
    ) -> Optional[str]:
        """Create or update a synced ROI in the target image"""
        try:
            # Check if synced ROI already exists
            pair_key = self._get_pair_key(source_index, target_index)
            existing_synced_id = None

            if (
                pair_key in self._roi_mappings
                and source_roi_id in self._roi_mappings[pair_key]
            ):
                existing_synced_id = self._roi_mappings[pair_key][source_roi_id]

            if existing_synced_id:
                # Update existing synced ROI
                return self._update_existing_synced_roi(
                    existing_synced_id, roi, target_index
                )
            else:
                # Create new synced ROI
                return self._create_new_synced_roi(roi, target_index)

        except Exception as e:
            logger.error(f"Error creating/updating synced ROI: {e}")
            return None

    def _create_new_synced_roi(self, roi, target_index: int) -> Optional[str]:
        """Create a new synced ROI in the target image"""
        try:
            roi_id = self.proj.roiManager.addROI(roi, [target_index])
            return roi_id

        except Exception as e:
            logger.error(f"Error creating new synced ROI: {e}")
            return None

    def _update_existing_synced_roi(
        self, synced_roi_id: str, roi, target_index: int
    ) -> Optional[str]:
        """Update an existing synced ROI"""
        try:
            success = self.proj.roiManager.updateROI(synced_roi_id, roi)
            return synced_roi_id if success else None

        except Exception as e:
            logger.error(f"Error updating synced ROI {synced_roi_id}: {e}")
            return None

    def _remove_synced_rois(self, primary_index: int, secondary_index: int):
        """Remove all synced ROIs when cleaning up"""
        pair_key = self._get_pair_key(primary_index, secondary_index)

        if pair_key in self._roi_mappings:
            for source_roi_id, synced_roi_id in self._roi_mappings[pair_key].items():
                try:
                    self.proj.roiManager.removeROI(synced_roi_id)
                except Exception as e:
                    logger.error(f"Error removing synced ROI {synced_roi_id}: {e}")

    def _sync_latest_rois(self, source_index: int, target_index: int):
        """Sync the latest ROIs from source to target"""
        try:
            source_rois = self.proj.roiManager.getROIsForImage(source_index)

            pair_key = self._get_pair_key(source_index, target_index)
            synced_roi_ids = set(self._roi_mappings.get(pair_key, {}).keys())

            # Sync any ROIs that haven't been synced yet
            for roi in source_rois:
                if hasattr(roi, "id") and roi.id not in synced_roi_ids:
                    self.sync_roi(roi.id, source_index, target_index)

        except Exception as e:
            logger.error(f"Error syncing latest ROIs: {e}")
