# src/core/stretch/stretch_manager.py

from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import logging

from core.entities.stretch import Stretch
from core.stretch.stretch_algorithms import compute_stretch, get_available_stretches, apply_stretch_transform

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
    def create_stretch_from_preset(preset_id: str, image_data: np.ndarray, name: str = None) -> Stretch:
        """Create a Stretch object using a preset algorithm.
        
        Args:
            preset_id: The ID of the preset to use
            image_data: The image data to compute the stretch for
            name: Optional name for the stretch (defaults to preset name)
            
        Returns:
            A new Stretch object with values computed by the algorithm
        """
        # Compute the stretch values
        try:
            transform_params = {}
            minR, maxR, minG, maxG, minB, maxB = compute_stretch(preset_id, image_data, **transform_params)
            
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
    def apply_preset_to_image(preset_id: str, image_data: np.ndarray) -> Tuple[np.ndarray, Stretch]:
        """Apply a preset algorithm to an image and return both the transformed image and the stretch.
        
        This is used for algorithms like decorrelation stretch that need to transform the image
        data differently than just applying min/max values.
        
        Args:
            preset_id: The ID of the preset to use
            image_data: The image data to transform
            
        Returns:
            Tuple of (transformed_image, stretch)
        """
        try:
            # Compute the stretch with parameters
            transform_params = {}
            stretch_values = compute_stretch(preset_id, image_data, **transform_params)
            
            # Apply any special transformations
            transformed_image = apply_stretch_transform(
                image_data, preset_id, stretch_values, **transform_params)
            
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
    def create_all_preset_stretches(image_data: np.ndarray) -> List[Stretch]:
        """Create a list of Stretch objects for all available presets.
        
        Args:
            image_data: The image data to compute stretches for
            
        Returns:
            List of Stretch objects
        """
        stretches = []
        
        for preset_id, preset_name in get_available_stretches():
            try:
                stretch = StretchPresets.create_stretch_from_preset(preset_id, image_data, preset_name)
                stretches.append(stretch)
            except Exception as e:
                logger.error(f"Error creating preset stretch {preset_name}: {e}")
                # Skip this preset on error
        
        # Ensure at least one stretch is returned
        if not stretches:
            stretches.append(Stretch.createDefault())
        
        return stretches