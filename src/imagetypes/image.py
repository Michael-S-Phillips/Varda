from abc import ABC, abstractmethod


class Image(ABC):
    """
    Abstract base class for all images in varda.
    Allows for a consistent interface with the images.
    """

    # dictionary of all subclasses of SpectralImage, mapped to their associated keyword
    subclasses = []

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        Image.subclasses.append(cls)

    @abstractmethod
    def process(self, process):
        """
        Executes a process on the image
        """
        pass

    @classmethod
    def __str__(cls):
        return "name: " + cls.__name__

    @classmethod
    def __repr__(cls):
        return "name: " + cls.__name__

    """
    Getters that all image subclasses must provide:
        data -  ndarray containing the raw image data
        meta -  Metadata dictionary
    """
    def get_image_slice(self, bands):
        try:
            return self.data[:, :, bands]
        except TypeError:
            raise TypeError("bands must be an iterable object (list, tuple, ndarray)")

    # @property @abstractmethod forces subclasses to create a variable with this name
    @property
    @abstractmethod
    def image_type(self):
        pass

    @property
    @abstractmethod
    def data(self):
        pass

    @property
    @abstractmethod
    def meta(self):
        pass

    @property
    @abstractmethod
    def uint8_data(self):
        pass
