from abc import ABC, abstractmethod


class ImageProcess(ABC):
    """Base class for processes"""

    subclasses = []

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
    def __str__(cls):
        return "name: " + cls.__name__

    @classmethod
    def __repr__(cls):
        return "name: " + cls.__name__
