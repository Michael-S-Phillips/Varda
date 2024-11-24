# standard library

# third party imports
from pathlib import Path

# local imports
from models.abstractimagemodel import AbstractImageModel


class ImageLoader:
    """
    determines which subclass is needed and returns a new instance of it
    """

    @classmethod
    def new_image(cls, file_path):
        # TODO: possibly need more complex system to determine file type? right now its just based on the file extension
        imageType = str(Path(file_path).suffix.strip())
        print(imageType)
        print(AbstractImageModel.subclasses)
        for c in AbstractImageModel.subclasses:
            if imageType in c.imageType:
                return c(file_path)
        raise ValueError(f"Bad file type {imageType}")
