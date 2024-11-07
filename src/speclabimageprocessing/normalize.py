# standard library
from typing import override

# third party imports
import numpy as np

# local imports
from speclabimageprocessing.imageprocess import ImageProcess

class Normalize(ImageProcess):

    @property
    def threshold(self):
        return self._threshold

    @threshold.setter
    def threshold(self, value):
        self._threshold = value

    def __init__(self):
        parameters = {
            'threshold': {'type': float, 'default': 0.0, 'description': 'Threshold value to be added to the minimum and subtracted from the maximum value of the image.'},
        }
        super().__init__()

    @override
    def execute(self, image, threshold=0.0):
        min_val = np.min(image) + threshold
        max_val = np.max(image) - threshold

        return np.clip((image - min_val) /  (max_val - min_val), 0, 1)