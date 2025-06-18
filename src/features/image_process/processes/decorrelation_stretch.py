# standard library
from typing import override

# third party imports
import numpy as np

# local imports
from features.image_process.processes.imageprocess import ImageProcess


class DecorrelationStretch(ImageProcess):
    """Decorrelation Stretch Process
    
    Applies a decorrelation stretch transformation to create a new enhanced image.
    This process uses Principal Component Analysis (PCA) to decorrelate RGB channels,
    enhancing subtle color differences in the image data.
    """

    name = "Decorrelation Stretch"
    
    # Specify that this process needs current RGB bands
    input_data_type = "current_rgb"

    # categorization path for the processing menu
    path = "Color Enhancement/Decorrelation Stretch"

    parameters = {
        "scaling_factor": {
            "type": float,
            "default": 2.5,
            "description": "Scaling factor for eigenvalues. Higher values increase "
            "color separation but may introduce artifacts. Range: 1.0-5.0",
        },
        "preserve_brightness": {
            "type": bool,
            "default": True,
            "description": "Preserve the original brightness of the image while "
            "enhancing color differences.",
        },
    }

    def __init__(self):
        super().__init__()

    @override
    def execute(self, image, scaling_factor=2.5, preserve_brightness=True):
        """Execute decorrelation stretch on the input image.
        
        Args:
            image: Input image array with shape (height, width, bands)
            scaling_factor: Scaling factor for eigenvalues
            preserve_brightness: Whether to preserve original brightness
            
        Returns:
            Transformed image array with enhanced color differences
        """
        if image.ndim != 3 or image.shape[2] < 3:
            raise ValueError(
                "Decorrelation stretch requires RGB image data with at least 3 bands"
            )

        # Use only the first 3 bands (RGB) for decorrelation
        rgb_data = image[:, :, :3].astype(np.float64)
        
        # Store original shape and additional bands if any
        original_shape = image.shape
        additional_bands = None
        if original_shape[2] > 3:
            additional_bands = image[:, :, 3:]

        # Apply decorrelation transformation
        transformed_rgb = self._apply_decorrelation_transform(
            rgb_data, scaling_factor, preserve_brightness
        )

        # Combine with additional bands if present
        if additional_bands is not None:
            result = np.concatenate([transformed_rgb, additional_bands], axis=2)
        else:
            result = transformed_rgb

        # Ensure output is in valid range [0, 1]
        return np.clip(result, 0, 1)

    def _apply_decorrelation_transform(
        self, rgb_data, scaling_factor, preserve_brightness
    ):
        """Apply the decorrelation transformation to RGB data.
        
        Args:
            rgb_data: RGB image data with shape (height, width, 3)
            scaling_factor: Scaling factor for eigenvalues
            preserve_brightness: Whether to preserve original brightness
            
        Returns:
            Transformed RGB data
        """
        h, w, c = rgb_data.shape
        pixels = h * w

        # Reshape to 2D for PCA: (pixels, channels)
        reshaped_data = rgb_data.reshape(pixels, c)

        # Remove NaN values if any
        valid_mask = ~np.isnan(reshaped_data).any(axis=1)
        if not np.all(valid_mask):
            # Handle NaN values by using only valid pixels for statistics
            valid_data = reshaped_data[valid_mask]
        else:
            valid_data = reshaped_data

        if valid_data.shape[0] == 0:
            raise ValueError("No valid pixel data found for decorrelation stretch")

        # Compute statistics
        mean_vec = np.nanmean(valid_data, axis=0)
        
        # Store original brightness if preserving
        if preserve_brightness:
            original_brightness = np.mean(reshaped_data, axis=1, keepdims=True)

        # Center the data
        centered_data = reshaped_data - mean_vec

        # Compute covariance matrix
        cov_mat = np.cov(valid_data, rowvar=False)

        # Eigendecomposition
        eigenvals, eigenvecs = np.linalg.eigh(cov_mat)

        # Sort eigenvalues and eigenvectors in descending order
        idx = eigenvals.argsort()[::-1]
        eigenvals = eigenvals[idx]
        eigenvecs = eigenvecs[:, idx]

        # Ensure eigenvalues are positive (numerical stability)
        eigenvals = np.maximum(eigenvals, 1e-10)

        # Transform to PCA space
        pca_data = np.dot(centered_data, eigenvecs)

        # Scale the data in PCA space
        scaled_eigenvals = eigenvals * scaling_factor
        scale_factors = np.sqrt(scaled_eigenvals / eigenvals)
        scaled_pca_data = pca_data * scale_factors

        # Transform back to RGB space
        transformed_data = np.dot(scaled_pca_data, eigenvecs.T) + mean_vec

        # Preserve brightness if requested
        if preserve_brightness:
            current_brightness = np.mean(transformed_data, axis=1, keepdims=True)
            # Avoid division by zero
            brightness_mask = current_brightness > 1e-10
            brightness_ratio = np.ones_like(current_brightness)
            brightness_ratio[brightness_mask] = (
                original_brightness[brightness_mask] 
                / current_brightness[brightness_mask]
            )
            transformed_data = transformed_data * brightness_ratio

        # Reshape back to image shape
        transformed_image = transformed_data.reshape(h, w, c)

        return transformed_image