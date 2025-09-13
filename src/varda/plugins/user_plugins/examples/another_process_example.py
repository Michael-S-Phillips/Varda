import varda
import logging
import numpy as np

logger = logging.getLogger(__name__)


@varda.plugins.hookimpl
def onLoad():
    logger.info("Plugin hook implementation called: another_process_example")
    varda.app.registry.registerImageProcess(ColorAdjustmentProcess)
    varda.app.registry.registerImageProcess(FilterProcess)


class ColorAdjustmentProcess:
    """
    A process for adjusting color properties of an image.
    """
    name = "Color/Adjustment/Color Adjustment"
    parameters = {
        "brightness": {
            "type": float,
            "default": 0.0,
            "min": -1.0,
            "max": 1.0,
            "description": "Adjust brightness of the image (-1 to 1)",
        },
        "contrast": {
            "type": float,
            "default": 1.0,
            "min": 0.5,
            "max": 2.0,
            "description": "Adjust contrast of the image (0.5 to 2)",
        },
        "apply_to_all_channels": {
            "type": bool,
            "default": True,
            "description": "Apply adjustments to all color channels",
        }
    }
    input_data_type = "full_raster"

    def execute(self, image, brightness=0.0, contrast=1.0, apply_to_all_channels=True):
        """
        Adjust brightness and contrast of the image.
        
        Args:
            image: The input image data
            brightness: Brightness adjustment (-1 to 1)
            contrast: Contrast adjustment (0.5 to 2)
            apply_to_all_channels: Whether to apply to all channels
            
        Returns:
            The processed image data
        """
        # Create a copy of the image to avoid modifying the original
        result = image.copy()
        
        # Apply brightness and contrast adjustments
        if apply_to_all_channels:
            # Apply to all channels
            result = result * contrast + brightness
        else:
            # Apply only to the first channel (assuming RGB)
            if result.ndim >= 3 and result.shape[2] >= 3:
                result[:, :, 0] = result[:, :, 0] * contrast + brightness
        
        return result


class FilterProcess:
    """
    A process for applying filters to an image.
    """
    name = "Filters/Blur"
    parameters = {
        "kernel_size": {
            "type": float,
            "default": 3.0,
            "min": 1.0,
            "max": 10.0,
            "description": "Size of the blur kernel",
        }
    }
    input_data_type = "full_raster"

    def execute(self, image, kernel_size=3.0):
        """
        Apply a simple blur filter to the image.
        
        Args:
            image: The input image data
            kernel_size: Size of the blur kernel
            
        Returns:
            The processed image data
        """
        # This is a simplified example - in a real implementation,
        # you would use a proper convolution or scipy/OpenCV for blurring
        
        # Create a copy of the image to avoid modifying the original
        result = image.copy()
        
        # Simulate a blur by averaging nearby pixels
        # (This is just for demonstration - not an efficient implementation)
        k = int(kernel_size)
        if k > 1:
            # Simple box blur simulation
            for _ in range(k):
                result = (np.roll(result, 1, axis=0) + 
                          np.roll(result, -1, axis=0) + 
                          np.roll(result, 1, axis=1) + 
                          np.roll(result, -1, axis=1)) / 4.0
        
        return result