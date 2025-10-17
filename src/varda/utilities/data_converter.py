"""
Data conversion utilities for robust spectral data handling.
Provides safe conversion with fallback strategies and validation.
"""

import numpy as np
import logging
from typing import Tuple, Optional, Union, Any

logger = logging.getLogger(__name__)


class DataConverter:
    """Utility class for safe data type conversion with fallback strategies."""

    @staticmethod
    def safe_array_conversion(
        data: Any,
        target_dtype: type = float,
        fallback_strategy: str = "zeros",
        expected_length: Optional[int] = None,
    ) -> Tuple[np.ndarray, bool, str]:
        """
        Safely convert data to numpy array with comprehensive error handling.

        Args:
            data: Input data to convert
            target_dtype: Target numpy data type
            fallback_strategy: Strategy for handling conversion failures
                - "zeros": Return zeros array
                - "ones": Return ones array
                - "random": Return random values
                - "interpolate": Attempt interpolation if partially valid
            expected_length: Expected array length for validation

        Returns:
            Tuple of (converted_array, success_flag, error_message)
        """
        error_message = ""

        try:
            # Handle None or empty input
            if data is None:
                error_message = "Input data is None"
                logger.warning(error_message)
                return (
                    DataConverter._create_fallback_array(
                        fallback_strategy, target_dtype, expected_length
                    ),
                    False,
                    error_message,
                )

            # Convert to numpy array
            try:
                array_data = np.asarray(data, dtype=target_dtype)
            except (ValueError, TypeError) as e:
                error_message = (
                    f"Failed to convert data to {target_dtype.__name__}: {e}"
                )
                logger.warning(error_message)

                # Try alternative conversion strategies
                array_data = DataConverter._attempt_alternative_conversion(
                    data, target_dtype, fallback_strategy, expected_length
                )
                if array_data is None:
                    return (
                        DataConverter._create_fallback_array(
                            fallback_strategy, target_dtype, expected_length
                        ),
                        False,
                        error_message,
                    )

            # Ensure 1D array
            if array_data.ndim > 1:
                original_shape = array_data.shape
                array_data = array_data.flatten()
                logger.info(
                    f"Flattened array from shape {original_shape} to {array_data.shape}"
                )

            # Validate array length if expected
            if expected_length is not None and len(array_data) != expected_length:
                error_message = f"Array length {len(array_data)} doesn't match expected {expected_length}"
                logger.warning(error_message)

                # Try to resize or pad the array
                array_data = DataConverter._resize_array(
                    array_data, expected_length, target_dtype
                )

            # Check for invalid values
            if target_dtype == float:
                invalid_mask = np.isnan(array_data) | np.isinf(array_data)
                if np.any(invalid_mask):
                    invalid_count = np.sum(invalid_mask)
                    logger.warning(
                        f"Found {invalid_count} invalid values, replacing with interpolation"
                    )
                    array_data = DataConverter._fix_invalid_values(
                        array_data, invalid_mask
                    )

            # Final validation
            if len(array_data) == 0:
                error_message = "Resulting array is empty"
                logger.error(error_message)
                return (
                    DataConverter._create_fallback_array(
                        fallback_strategy, target_dtype, expected_length
                    ),
                    False,
                    error_message,
                )

            logger.debug(
                f"Successfully converted data to {target_dtype.__name__} array of length {len(array_data)}"
            )
            return array_data, True, ""

        except Exception as e:
            error_message = f"Unexpected error during data conversion: {e}"
            logger.error(error_message)
            return (
                DataConverter._create_fallback_array(
                    fallback_strategy, target_dtype, expected_length
                ),
                False,
                error_message,
            )

    @staticmethod
    def _attempt_alternative_conversion(
        data: Any,
        target_dtype: type,
        fallback_strategy: str,
        expected_length: Optional[int],
    ) -> Optional[np.ndarray]:
        """Attempt alternative conversion strategies."""
        try:
            # Strategy 1: Try converting as string first, then to target type
            if hasattr(data, "__iter__") and not isinstance(data, str):
                try:
                    str_data = [str(item).strip() for item in data]
                    converted = np.asarray(str_data, dtype=target_dtype)
                    logger.info("Successfully converted via string intermediate")
                    return converted
                except (ValueError, TypeError):
                    pass

            # Strategy 2: Try element-by-element conversion
            if hasattr(data, "__iter__") and not isinstance(data, str):
                converted_items = []
                for item in data:
                    try:
                        converted_items.append(target_dtype(item))
                    except (ValueError, TypeError):
                        # Use a default value for failed conversions
                        if target_dtype == float:
                            converted_items.append(0.0)
                        elif target_dtype == int:
                            converted_items.append(0)
                        else:
                            converted_items.append(target_dtype())

                if converted_items:
                    logger.info(
                        "Successfully converted via element-by-element conversion"
                    )
                    return np.asarray(converted_items, dtype=target_dtype)

            # Strategy 3: Try to extract numeric values from strings
            if target_dtype == float and hasattr(data, "__iter__"):
                import re

                numeric_pattern = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)")
                converted_items = []

                for item in data:
                    str_item = str(item)
                    matches = numeric_pattern.findall(str_item)
                    if matches:
                        try:
                            converted_items.append(float(matches[0]))
                        except ValueError:
                            converted_items.append(0.0)
                    else:
                        converted_items.append(0.0)

                if converted_items:
                    logger.info("Successfully converted via regex extraction")
                    return np.asarray(converted_items, dtype=target_dtype)

        except Exception as e:
            logger.debug(f"Alternative conversion strategy failed: {e}")

        return None

    @staticmethod
    def _resize_array(
        array_data: np.ndarray, target_length: int, dtype: type
    ) -> np.ndarray:
        """Resize array to target length using appropriate strategy."""
        current_length = len(array_data)

        if current_length > target_length:
            # Truncate array
            logger.info(f"Truncating array from {current_length} to {target_length}")
            return array_data[:target_length]

        elif current_length < target_length:
            # Pad array
            pad_length = target_length - current_length

            if current_length > 0:
                # Pad with last value
                pad_value = array_data[-1]
                padding = np.full(pad_length, pad_value, dtype=dtype)
                logger.info(
                    f"Padding array from {current_length} to {target_length} with value {pad_value}"
                )
            else:
                # Pad with zeros
                padding = np.zeros(pad_length, dtype=dtype)
                logger.info(f"Padding empty array to length {target_length} with zeros")

            return np.concatenate([array_data, padding])

        return array_data

    @staticmethod
    def _fix_invalid_values(
        array_data: np.ndarray, invalid_mask: np.ndarray
    ) -> np.ndarray:
        """Fix invalid values using interpolation or replacement."""
        fixed_array = array_data.copy()

        # Get valid indices
        valid_indices = np.where(~invalid_mask)[0]
        invalid_indices = np.where(invalid_mask)[0]

        if len(valid_indices) == 0:
            # All values are invalid, replace with zeros
            logger.warning("All values are invalid, replacing with zeros")
            fixed_array[:] = 0.0
        elif len(valid_indices) == 1:
            # Only one valid value, use it for all invalid positions
            valid_value = fixed_array[valid_indices[0]]
            fixed_array[invalid_indices] = valid_value
            logger.info(
                f"Replaced {len(invalid_indices)} invalid values with {valid_value}"
            )
        else:
            # Interpolate invalid values
            try:
                fixed_array[invalid_indices] = np.interp(
                    invalid_indices, valid_indices, fixed_array[valid_indices]
                )
                logger.info(f"Interpolated {len(invalid_indices)} invalid values")
            except Exception as e:
                logger.warning(f"Interpolation failed: {e}, using nearest valid value")
                # Fallback: use nearest valid value
                for idx in invalid_indices:
                    nearest_valid_idx = valid_indices[
                        np.argmin(np.abs(valid_indices - idx))
                    ]
                    fixed_array[idx] = fixed_array[nearest_valid_idx]

        return fixed_array

    @staticmethod
    def _create_fallback_array(
        strategy: str, dtype: type, length: Optional[int]
    ) -> np.ndarray:
        """Create fallback array based on strategy."""
        if length is None or length <= 0:
            length = 100  # Default length

        if strategy == "zeros":
            return np.zeros(length, dtype=dtype)
        elif strategy == "ones":
            return np.ones(length, dtype=dtype)
        elif strategy == "random":
            if dtype == float:
                return np.random.random(length).astype(dtype)
            else:
                return np.random.randint(0, 100, length).astype(dtype)
        else:
            # Default to zeros
            return np.zeros(length, dtype=dtype)

    @staticmethod
    def validate_spectral_data_compatibility(
        wavelengths: np.ndarray, values: np.ndarray
    ) -> Tuple[bool, str, Optional[Tuple[np.ndarray, np.ndarray]]]:
        """
        Validate that wavelength and spectral value arrays are compatible.

        Args:
            wavelengths: Wavelength array
            values: Spectral values array

        Returns:
            Tuple of (is_compatible, error_message, corrected_arrays)
        """
        try:
            if len(wavelengths) == len(values):
                return True, "", None

            error_msg = f"Length mismatch: wavelengths ({len(wavelengths)}) vs values ({len(values)})"
            logger.warning(error_msg)

            # Attempt correction
            min_length = min(len(wavelengths), len(values))
            if min_length > 0:
                corrected_wavelengths = wavelengths[:min_length]
                corrected_values = values[:min_length]
                logger.info(f"Truncated arrays to common length: {min_length}")
                return (
                    True,
                    f"Arrays truncated to length {min_length}",
                    (corrected_wavelengths, corrected_values),
                )
            else:
                return False, "Both arrays are empty", None

        except Exception as e:
            error_msg = f"Error validating data compatibility: {e}"
            logger.error(error_msg)
            return False, error_msg, None
