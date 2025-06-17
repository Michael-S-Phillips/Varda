# src/core/stretch/stretch_manager.py

from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import logging

from core.entities.stretch import Stretch
from core.stretch.stretch_algorithms import (
    compute_stretch,
    get_available_stretches,
    apply_stretch_transform,
)

logger = logging.getLogger(__name__)


class StretchPresets:
    """Utility class to manage stretch presets and create Stretch objects."""

    @staticmethod
    def get_preset_names() -> List[Tuple[str, str]]:
        """Get a list of available preset names.

        Returns:
            List of tuples (algorithm_id, display_name)
        """
        return get_available_stretches()

    @staticmethod
    def create_stretch_from_preset(
        preset_id: str, image_data: np.ndarray, band_config: 'Band' = None, name: str = None
    ) -> Stretch:
        """Create a Stretch object using a preset algorithm.

        Args:
            preset_id: The ID of the preset to use
            image_data: The full hyperspectral image data
            band_config: Band configuration specifying which bands to use for RGB
            name: Optional name for the stretch (defaults to preset name)

        Returns:
            A new Stretch object with values computed by the algorithm
        """
        # Extract only the RGB bands if band_config is provided
        if band_config is not None:
            try:
                # Extract the specific RGB bands for stretch calculation
                rgb_data = image_data[:, :, [band_config.r, band_config.g, band_config.b]]
            except IndexError as e:
                logger.error(f"Error extracting RGB bands {[band_config.r, band_config.g, band_config.b]}: {e}")
                # Fall back to first 3 bands if extraction fails
                rgb_data = image_data[:, :, :3] if image_data.shape[2] >= 3 else image_data
        else:
            # Fall back to first 3 bands if no band config provided
            rgb_data = image_data[:, :, :3] if image_data.shape[2] >= 3 else image_data
        
        # Compute the stretch values on the RGB data
        try:
            transform_params = {}
            minR, maxR, minG, maxG, minB, maxB = compute_stretch(
                preset_id, rgb_data, **transform_params
            )

            # Create a stretch name if not provided
            if name is None:
                presets = dict(get_available_stretches())
                if preset_id in presets:
                    name = presets[preset_id]
                else:
                    name = "Custom Stretch"

            # Create and return the Stretch object
            return Stretch(name, minR, maxR, minG, maxG, minB, maxB)

        except Exception as e:
            logger.error(f"Error creating stretch from preset {preset_id}: {e}")
            # Fall back to default stretch on error
            return Stretch.createDefault()

    @staticmethod
    def apply_preset_to_image(
        preset_id: str, image_data: np.ndarray, band_config: 'Band' = None
    ) -> Tuple[np.ndarray, Stretch]:
        """Apply a preset algorithm to an image and return both the transformed image and the stretch.

        This is used for algorithms like decorrelation stretch that need to transform the image
        data differently than just applying min/max values.

        Args:
            preset_id: The ID of the preset to use
            image_data: The full hyperspectral image data
            band_config: Band configuration specifying which bands to use for RGB

        Returns:
            Tuple of (transformed_image, stretch)
        """
        try:
            # Extract only the RGB bands if band_config is provided
            if band_config is not None:
                try:
                    # Extract the specific RGB bands for stretch calculation
                    rgb_data = image_data[:, :, [band_config.r, band_config.g, band_config.b]]
                except IndexError as e:
                    logger.error(f"Error extracting RGB bands {[band_config.r, band_config.g, band_config.b]}: {e}")
                    # Fall back to first 3 bands if extraction fails
                    rgb_data = image_data[:, :, :3] if image_data.shape[2] >= 3 else image_data
            else:
                # Fall back to first 3 bands if no band config provided
                rgb_data = image_data[:, :, :3] if image_data.shape[2] >= 3 else image_data

            # Compute the stretch with parameters on RGB data
            transform_params = {}
            stretch_values = compute_stretch(preset_id, rgb_data, **transform_params)

            # Apply any special transformations to the RGB data
            transformed_rgb = apply_stretch_transform(
                rgb_data, preset_id, stretch_values, **transform_params
            )

            # For the final output, we need to return the full image with only RGB bands transformed
            # if we have a band config, otherwise return the transformed RGB data
            if band_config is not None and transformed_rgb.shape == rgb_data.shape:
                # Create a copy of the original image and replace the RGB bands
                transformed_image = image_data.copy()
                transformed_image[:, :, [band_config.r, band_config.g, band_config.b]] = transformed_rgb
            else:
                transformed_image = transformed_rgb

            # Create a stretch name
            presets = dict(get_available_stretches())
            if preset_id in presets:
                name = presets[preset_id]
            else:
                name = "Custom Stretch"

            # Create the Stretch object
            minR, maxR, minG, maxG, minB, maxB = stretch_values
            stretch = Stretch(name, minR, maxR, minG, maxG, minB, maxB)

            return transformed_image, stretch

        except Exception as e:
            logger.error(f"Error applying preset {preset_id} to image: {e}")
            # Fall back to original image and default stretch on error
            return image_data, Stretch.createDefault()

    @staticmethod
    def create_all_preset_stretches(image_data: np.ndarray, band_config: 'Band' = None) -> List[Stretch]:
        """Create a list of Stretch objects for all available presets.

        Args:
            image_data: The full hyperspectral image data
            band_config: Band configuration specifying which bands to use for RGB

        Returns:
            List of Stretch objects
        """
        stretches = []

        for preset_id, preset_name in get_available_stretches():
            try:
                stretch = StretchPresets.create_stretch_from_preset(
                    preset_id, image_data, band_config, preset_name
                )
                stretches.append(stretch)
            except Exception as e:
                logger.error(f"Error creating preset stretch {preset_name}: {e}")
                # Skip this preset on error

        # Ensure at least one stretch is returned
        if not stretches:
            stretches.append(Stretch.createDefault())

        return stretches
