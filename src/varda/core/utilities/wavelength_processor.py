"""
Wavelength data processing utilities for spectral plotting.
Provides consistent wavelength handling across all plotting components.
"""

import numpy as np
import logging
from typing import Tuple, Union

logger = logging.getLogger(__name__)


class WavelengthProcessor:
    """Utility class for processing and validating wavelength data."""
    
    @staticmethod
    def process_wavelength_data(
        wavelengths: Union[np.ndarray, list, None], 
        band_count: int
    ) -> Tuple[np.ndarray, str]:
        """
        Process wavelength data with consistent validation and fallback logic.
        
        Args:
            wavelengths: Raw wavelength data from image metadata
            band_count: Number of spectral bands
            
        Returns:
            Tuple of (processed_wavelengths, wavelength_type)
            wavelength_type: 'numeric', 'categorical', or 'indices'
        """
        try:
            # Handle None or empty wavelengths
            if wavelengths is None or len(wavelengths) == 0:
                logger.warning("No wavelength data provided, using band indices")
                return np.arange(band_count, dtype=float), 'indices'
            
            # Ensure wavelengths is a numpy array
            wavelengths = np.asarray(wavelengths)
            
            # Handle multi-dimensional arrays
            if wavelengths.ndim > 1:
                wavelengths = wavelengths.flatten()
            
            # Check if band count matches
            if len(wavelengths) != band_count:
                logger.warning(
                    f"Wavelength count ({len(wavelengths)}) doesn't match band count ({band_count}), "
                    "using band indices"
                )
                return np.arange(band_count, dtype=float), 'indices'
            
            # Attempt numeric conversion
            try:
                # Handle string arrays that might contain numeric values
                if wavelengths.dtype.kind in ['U', 'S', 'O']:  # Unicode, byte string, or object
                    # Strip whitespace and attempt conversion
                    numeric_wavelengths = np.char.strip(wavelengths.astype(str)).astype(float)
                    
                    # Validate converted values
                    if np.any(np.isnan(numeric_wavelengths)) or np.any(np.isinf(numeric_wavelengths)):
                        raise ValueError("Invalid numeric values detected")
                    
                    logger.debug("Successfully converted string wavelengths to numeric")
                    return numeric_wavelengths.astype(float), 'numeric'
                
                else:
                    # Already numeric, validate and convert
                    numeric_wavelengths = wavelengths.astype(float)
                    
                    # Check for invalid values
                    if np.any(np.isnan(numeric_wavelengths)) or np.any(np.isinf(numeric_wavelengths)):
                        raise ValueError("Invalid numeric values in wavelength data")
                    
                    logger.debug("Using existing numeric wavelengths")
                    return numeric_wavelengths, 'numeric'
                    
            except (ValueError, TypeError) as e:
                logger.info(f"Could not convert wavelengths to numeric: {e}")
                
                # Check if we can use as categorical labels
                if wavelengths.dtype.kind in ['U', 'S', 'O']:
                    logger.info("Using wavelengths as categorical labels")
                    return np.arange(band_count, dtype=float), 'categorical'
                else:
                    # Fallback to band indices
                    logger.warning("Falling back to band indices for wavelengths")
                    return np.arange(band_count, dtype=float), 'indices'
                    
        except Exception as e:
            logger.error(f"Error processing wavelength data: {e}")
            logger.warning("Using band indices as fallback")
            return np.arange(band_count, dtype=float), 'indices'
    
    @staticmethod
    def get_wavelength_label(wavelength_type: str) -> str:
        """Get appropriate axis label based on wavelength type."""
        if wavelength_type == 'numeric':
            return "Wavelength (nm)"
        elif wavelength_type == 'categorical':
            return "Band Name"
        else:  # indices
            return "Band Number"
    
    @staticmethod
    def format_wavelength_info(wavelengths: np.ndarray, wavelength_type: str) -> str:
        """Format wavelength range information for logging."""
        if wavelength_type == 'numeric' and len(wavelengths) > 0:
            return f"{wavelengths.min():.2f} - {wavelengths.max():.2f} nm"
        elif len(wavelengths) > 0:
            return f"Bands 0 - {len(wavelengths) - 1}"
        else:
            return "No wavelength data"