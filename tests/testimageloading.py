import unittest

import os
from pathlib import Path
import features.image_load as image_loader


class TestBackend(unittest.TestCase):

    def testImageLoadingFeature(self):
        image_loader.loadNewImage("")


if __name__ == '__main__':
    unittest.main()
