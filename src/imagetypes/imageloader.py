# standard library

# third party imports
from pathlib import Path

# local imports
from imagetypes.image import Image


class ImageLoader:
    """
    determines which subclass is needed and returns a new instance of it
    """

    @classmethod
    def new_image(cls, file_path):
        # TODO: possibly need more complex system to determine file type? right now its just based on the file extension
        image_type = str(Path(file_path).suffix.strip())
        print(image_type)
        print(Image.subclasses)
        for c in Image.subclasses:
            if c.image_type == image_type:
                return c(file_path)
        raise ValueError(f"Bad file type {image_type}")
