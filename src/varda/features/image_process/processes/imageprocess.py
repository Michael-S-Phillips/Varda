from abc import ABC, abstractmethod


class ImageProcess(ABC):
    """Base class for processes"""

    subclasses = []

    # Class attribute to define what data the process needs
    input_data_type = "full_raster"  # Options: "full_raster", "current_rgb", "custom"

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        ImageProcess.subclasses.append(cls)
        print("ImageProcess subclass added")
        print(ImageProcess.subclasses)

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def path(self):
        pass

    @property
    @abstractmethod
    def parameters(self):
        pass

    @abstractmethod
    def execute(self, image):
        pass

    @classmethod
    def get_input_data(cls, image_obj):
        """Get the appropriate input data for this process.

        Args:
            image_obj: The Image object from the project

        Returns:
            np.ndarray: The data this process needs
        """
        if cls.input_data_type == "current_rgb":
            # Get RGB data from current band configuration
            current_band = image_obj.band[0]  # Use first band configuration
            rgb_indices = [current_band.r, current_band.g, current_band.b]
            return image_obj.raster[:, :, rgb_indices]
        elif cls.input_data_type == "full_raster":
            # Return the complete hyperspectral cube
            return image_obj.raster
        else:
            # For custom implementations, just return full raster by default
            return image_obj.raster

    @classmethod
    def __str__(cls):
        return "name: " + cls.__name__

    @classmethod
    def __repr__(cls):
        return "name: " + cls.__name__
