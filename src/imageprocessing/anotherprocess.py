# standard library
from typing import override

# third party imports
import numpy as np

# local imports
from imageprocessing.imageprocess import ImageProcess


class AnotherProcess(ImageProcess):

    name = "Another Process"

    # not being used yet. will be used for categorization
    path = "Special Processing/Another Process"

    parameters = {
        'A unique parameter ': {'type': float, 'default': 105.0,
                       'description': 'A parameter dynamically created for this '
                                      'specific process.'},
        'Another parameter': {'type': bool, 'default': True,
                              'description': 'Another parameter.'},
    }

    def __init__(self):
        super().__init__()

    @override
    def execute(self, image):
        return image
