"""
Invalid data handling utilities for consistent NaN/Inf value processing.
Provides standardized handling of invalid values across all spectral data operations.
"""

import numpy as np
import logging
from typing import Tuple, Optional, Union, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class InvalidValueStrategy(Enum):
    """Strategies for handling invalid values in spectral data."""
    INTERPOLATE = "interpolate"
    ZERO_FILL = "zero_fill"
    MEAN_FILL = "mean_fill"
    MEDIAN_FILL = "median_fill"
    REMOVE_INVALID = "remove_invalid"
    FORWARD_FILL = "forward_fill"
    BACKWARD_FILL = "backward_fill"
    NEAREST_FILL = "nearest_fill"


class InvalidDataHandler:
    """Utility class for detecting and handling invalid values in spectral data."""
    
    @staticmethod
    def detect_invalid_values(data: np.ndarray) -> Tuple[np.ndarray, Dict[str, int]]:
        """
        Detect various types of invalid values in array data.
        
        Args:
            data: Input array to check
            
        Returns:
            Tuple of (invalid_mask, statistics_dict)
        """
        try:
            data = np.asarray(data)
            
            # Create masks for different types of invalid values
            nan_mask = np.isnan(data)
            inf_mask = np.isinf(data)
            finite_mask = np.isfinite(data)
            
            # Combined invalid mask
            invalid_mask = ~finite_mask
            
            # Calculate statistics
            stats = {
                'total_values': len(data),
                'nan_count': np.sum(nan_mask),
                'inf_count': np.sum(inf_mask),
                'invalid_count': np.sum(invalid_mask),
                'valid_count': np.sum(finite_mask),
                'valid_percentage': (np.sum(finite_mask) / len(data)) * 100 if len(data) > 0 else 0
            }
            
            logger.debug(
                f"Invalid value detection: {stats['invalid_count']}/{stats['total_values']} "
                f"invalid ({stats['valid_percentage']:.1f}% valid)"
            )
            
            return invalid_mask, stats
            
        except Exception as e:
            logger.error(f"Error detecting invalid values: {e}")
            # Return safe defaults
            return np.zeros(len(data), dtype=bool), {
                'total_values': len(data),
                'nan_count': 0,
                'inf_count': 0,
                'invalid_count': 0,
                'valid_count': len(data),
                'valid_percentage': 100.0
            }
    
    @staticmethod
    def handle_invalid_values(
        data: np.ndarray,
        strategy: InvalidValueStrategy = InvalidValueStrategy.INTERPOLATE,
        preserve_shape: bool = True
    ) -> Tuple[np.ndarray, bool, str]:
        """
        Handle invalid values in array data using specified strategy.
        
        Args:
            data: Input array with potential invalid values
            strategy: Strategy for handling invalid values
            preserve_shape: Whether to preserve original array shape
            
        Returns:
            Tuple of (cleaned_data, success_flag, info_message)
        """
        try:
            data = np.asarray(data, dtype=float)
            original_shape = data.shape
            
            # Flatten for easier processing
            flat_data = data.flatten() if data.ndim > 1 else data.copy()
            
            # Detect invalid values
            invalid_mask, stats = InvalidDataHandler.detect_invalid_values(flat_data)
            
            if stats['invalid_count'] == 0:
                # No invalid values found
                return data, True, "No invalid values detected"
            
            if stats['valid_count'] == 0:
                # All values are invalid
                logger.warning("All values are invalid, creating fallback data")
                fallback_data = np.zeros_like(flat_data)
                if preserve_shape and data.ndim > 1:
                    fallback_data = fallback_data.reshape(original_shape)
                return fallback_data, False, "All values were invalid, replaced with zeros"
            
            # Apply the selected strategy
            cleaned_data, success, message = InvalidDataHandler._apply_strategy(
                flat_data, invalid_mask, strategy, stats
            )
            
            # Restore original shape if needed
            if preserve_shape and data.ndim > 1:
                try:
                    cleaned_data = cleaned_data.reshape(original_shape)
                except ValueError:
                    logger.warning("Could not restore original shape, returning flattened data")
            
            return cleaned_data, success, message
            
        except Exception as e:
            logger.error(f"Error handling invalid values: {e}")
            # Return safe fallback
            fallback_data = np.zeros_like(data, dtype=float)
            return fallback_data, False, f"Error processing invalid values: {str(e)}"
    
    @staticmethod
    def _apply_strategy(
        data: np.ndarray,
        invalid_mask: np.ndarray,
        strategy: InvalidValueStrategy,
        stats: Dict[str, int]
    ) -> Tuple[np.ndarray, bool, str]:
        """Apply the specified invalid value handling strategy."""
        cleaned_data = data.copy()
        invalid_indices = np.where(invalid_mask)[0]
        valid_indices = np.where(~invalid_mask)[0]
        
        try:
            if strategy == InvalidValueStrategy.INTERPOLATE:
                if len(valid_indices) >= 2:
                    # Linear interpolation
                    cleaned_data[invalid_indices] = np.interp(
                        invalid_indices, valid_indices, data[valid_indices]
                    )
                    message = f"Interpolated {len(invalid_indices)} invalid values"
                elif len(valid_indices) == 1:
                    # Use the single valid value
                    cleaned_data[invalid_indices] = data[valid_indices[0]]
                    message = f"Filled {len(invalid_indices)} invalid values with single valid value"
                else:
                    # No valid values for interpolation
                    cleaned_data[invalid_indices] = 0.0
                    message = f"No valid values for interpolation, filled with zeros"
                    
            elif strategy == InvalidValueStrategy.ZERO_FILL:
                cleaned_data[invalid_indices] = 0.0
                message = f"Filled {len(invalid_indices)} invalid values with zeros"
                
            elif strategy == InvalidValueStrategy.MEAN_FILL:
                if len(valid_indices) > 0:
                    mean_value = np.mean(data[valid_indices])
                    cleaned_data[invalid_indices] = mean_value
                    message = f"Filled {len(invalid_indices)} invalid values with mean ({mean_value:.3f})"
                else:
                    cleaned_data[invalid_indices] = 0.0
                    message = f"No valid values for mean, filled with zeros"
                    
            elif strategy == InvalidValueStrategy.MEDIAN_FILL:
                if len(valid_indices) > 0:
                    median_value = np.median(data[valid_indices])
                    cleaned_data[invalid_indices] = median_value
                    message = f"Filled {len(invalid_indices)} invalid values with median ({median_value:.3f})"
                else:
                    cleaned_data[invalid_indices] = 0.0
                    message = f"No valid values for median, filled with zeros"
                    
            elif strategy == InvalidValueStrategy.FORWARD_FILL:
                for idx in invalid_indices:
                    # Find previous valid value
                    prev_valid = valid_indices[valid_indices < idx]
                    if len(prev_valid) > 0:
                        cleaned_data[idx] = data[prev_valid[-1]]
                    else:
                        cleaned_data[idx] = 0.0
                message = f"Forward filled {len(invalid_indices)} invalid values"
                
            elif strategy == InvalidValueStrategy.BACKWARD_FILL:
                for idx in invalid_indices:
                    # Find next valid value
                    next_valid = valid_indices[valid_indices > idx]
                    if len(next_valid) > 0:
                        cleaned_data[idx] = data[next_valid[0]]
                    else:
                        cleaned_data[idx] = 0.0
                message = f"Backward filled {len(invalid_indices)} invalid values"
                
            elif strategy == InvalidValueStrategy.NEAREST_FILL:
                for idx in invalid_indices:
                    if len(valid_indices) > 0:
                        nearest_idx = valid_indices[np.argmin(np.abs(valid_indices - idx))]
                        cleaned_data[idx] = data[nearest_idx]
                    else:
                        cleaned_data[idx] = 0.0
                message = f"Filled {len(invalid_indices)} invalid values with nearest neighbors"
                
            elif strategy == InvalidValueStrategy.REMOVE_INVALID:
                # Return only valid data points
                cleaned_data = data[valid_indices]
                message = f"Removed {len(invalid_indices)} invalid values, kept {len(valid_indices)} valid values"
                
            else:
                # Default to zero fill
                cleaned_data[invalid_indices] = 0.0
                message = f"Unknown strategy, filled {len(invalid_indices)} invalid values with zeros"
            
            logger.debug(message)
            return cleaned_data, True, message
            
        except Exception as e:
            logger.error(f"Error applying strategy {strategy.value}: {e}")
            # Fallback to zero fill
            cleaned_data[invalid_indices] = 0.0
            return cleaned_data, False, f"Strategy failed, used zero fill: {str(e)}"
    
    @staticmethod
    def handle_spectral_pair(
        wavelengths: np.ndarray,
        values: np.ndarray,
        strategy: InvalidValueStrategy = InvalidValueStrategy.INTERPOLATE,
        sync_removal: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, bool, str]:
        """
        Handle invalid values in paired wavelength and spectral value arrays.
        
        Args:
            wavelengths: Wavelength array
            values: Spectral values array
            strategy: Strategy for handling invalid values
            sync_removal: If True, remove corresponding indices when either array has invalid values
            
        Returns:
            Tuple of (clean_wavelengths, clean_values, success_flag, info_message)
        """
        try:
            wavelengths = np.asarray(wavelengths, dtype=float)
            values = np.asarray(values, dtype=float)
            
            # Ensure arrays have same length
            min_length = min(len(wavelengths), len(values))
            wavelengths = wavelengths[:min_length]
            values = values[:min_length]
            
            # Detect invalid values in both arrays
            wl_invalid_mask, wl_stats = InvalidDataHandler.detect_invalid_values(wavelengths)
            val_invalid_mask, val_stats = InvalidDataHandler.detect_invalid_values(values)
            
            total_invalid = wl_stats['invalid_count'] + val_stats['invalid_count']
            
            if total_invalid == 0:
                return wavelengths, values, True, "No invalid values in spectral pair"
            
            if sync_removal and strategy == InvalidValueStrategy.REMOVE_INVALID:
                # Remove indices where either array has invalid values
                combined_invalid = wl_invalid_mask | val_invalid_mask
                valid_mask = ~combined_invalid
                
                clean_wavelengths = wavelengths[valid_mask]
                clean_values = values[valid_mask]
                
                removed_count = np.sum(combined_invalid)
                message = f"Removed {removed_count} synchronized invalid points, kept {len(clean_wavelengths)} valid points"
                
                return clean_wavelengths, clean_values, True, message
            
            else:
                # Handle each array independently
                clean_wavelengths, wl_success, wl_message = InvalidDataHandler.handle_invalid_values(
                    wavelengths, strategy
                )
                clean_values, val_success, val_message = InvalidDataHandler.handle_invalid_values(
                    values, strategy
                )
                
                success = wl_success and val_success
                message = f"Wavelengths: {wl_message}; Values: {val_message}"
                
                return clean_wavelengths, clean_values, success, message
                
        except Exception as e:
            logger.error(f"Error handling spectral pair: {e}")
            # Return safe fallback
            safe_length = max(len(wavelengths), len(values), 1)
            return (
                np.arange(safe_length, dtype=float),
                np.zeros(safe_length, dtype=float),
                False,
                f"Error processing spectral pair: {str(e)}"
            )
    
    @staticmethod
    def validate_spectral_data_quality(
        wavelengths: np.ndarray,
        values: np.ndarray,
        min_valid_percentage: float = 50.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the overall quality of spectral data.
        
        Args:
            wavelengths: Wavelength array
            values: Spectral values array
            min_valid_percentage: Minimum percentage of valid data required
            
        Returns:
            Tuple of (is_good_quality, quality_report)
        """
        try:
            wl_invalid_mask, wl_stats = InvalidDataHandler.detect_invalid_values(wavelengths)
            val_invalid_mask, val_stats = InvalidDataHandler.detect_invalid_values(values)
            
            quality_report = {
                'wavelength_stats': wl_stats,
                'values_stats': val_stats,
                'overall_valid_percentage': min(wl_stats['valid_percentage'], val_stats['valid_percentage']),
                'length_match': len(wavelengths) == len(values),
                'has_monotonic_wavelengths': False,
                'has_reasonable_range': False,
                'quality_issues': []
            }
            
            # Check if wavelengths are monotonic (for valid indices)
            if wl_stats['valid_count'] > 1:
                valid_wl = wavelengths[~wl_invalid_mask]
                quality_report['has_monotonic_wavelengths'] = np.all(np.diff(valid_wl) > 0) or np.all(np.diff(valid_wl) < 0)
            
            # Check for reasonable spectral value range
            if val_stats['valid_count'] > 0:
                valid_values = values[~val_invalid_mask]
                value_range = np.max(valid_values) - np.min(valid_values)
                quality_report['has_reasonable_range'] = value_range > 0
            
            # Collect quality issues
            if quality_report['overall_valid_percentage'] < min_valid_percentage:
                quality_report['quality_issues'].append(
                    f"Low data quality: {quality_report['overall_valid_percentage']:.1f}% valid (minimum: {min_valid_percentage}%)"
                )
            
            if not quality_report['length_match']:
                quality_report['quality_issues'].append("Wavelength and value array length mismatch")
            
            if not quality_report['has_monotonic_wavelengths']:
                quality_report['quality_issues'].append("Wavelengths are not monotonic")
            
            if not quality_report['has_reasonable_range']:
                quality_report['quality_issues'].append("Spectral values have no variance")
            
            is_good_quality = (
                quality_report['overall_valid_percentage'] >= min_valid_percentage and
                quality_report['length_match'] and
                len(quality_report['quality_issues']) == 0
            )
            
            return is_good_quality, quality_report
            
        except Exception as e:
            logger.error(f"Error validating spectral data quality: {e}")
            return False, {
                'error': str(e),
                'quality_issues': [f"Validation error: {str(e)}"]
            }