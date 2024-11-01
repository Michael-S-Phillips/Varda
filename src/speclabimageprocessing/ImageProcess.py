from abc import ABC, abstractmethod


class ImageProcess(ABC):
    subclasses = []

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        ImageProcess.subclasses.append(cls)


    @abstractmethod
    def execute(self, image):
        pass