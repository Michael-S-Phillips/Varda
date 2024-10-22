from abc import ABC, abstractmethod


class Image(ABC):
    """
    Abstract base class for all images in varda.
    Allows for a consistent interface with the images.
    """

    # dictionary of all subclasses of SpectralImage, mapped to their associated keyword
    subclasses = []

    # this forces subclasses to set this value
    @property
    @abstractmethod
    def image_type(self):
        pass

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        Image.subclasses.append(cls)

    @abstractmethod
    def request_rgb_data(self, bands):
        pass

    """
    Getters that all image subclasses must provide:
        data -  ndarray containing the raw image data
        meta -  Metadata dictionary
    """

    @property
    @abstractmethod
    def data(self):
        pass

    @property
    @abstractmethod
    def meta(self):
        pass
