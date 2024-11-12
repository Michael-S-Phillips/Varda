# standard library
from typing import override

# third party imports
import numpy as np

# local imports
from imageprocessing.imageprocess import ImageProcess


class MakeImageGood(ImageProcess):

    name = "Goodizer"

    # not being used yet. will be used for categorization
    path = "Super Special Processing/Goodizer"

    parameters = {
        'goodness': {'type': float, 'default': 105.0,
                     'description': 'level of goodness to apply to the image.'},
        'Extra Good': {'type': bool, 'default': True,
                       'description': 'Utilize generative AI to make the level of '
                                      'goodness exceed human comprehension'},
    }

    def __init__(self):
        super().__init__()

    @override
    def execute(self, image):
        return image
