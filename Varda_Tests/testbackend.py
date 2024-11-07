import unittest

import os
from pathlib import Path
from imagetypes import *


class TestBackend(unittest.TestCase):

    def testMetadata1(self):
        meta = Metadata("driver1", "dtype1", "dataignore1", "width1", "height1",
                        "bandcount1", "default_bands1", "transform1",
                        bonusMetadata="yoo imma bonus")
        for key, value in meta:
            print(key, "\n - ", value)
            pass

        print(meta.dtype)
        print(meta.bonusMetadata)

    def testENVIImage(self):
        image = ENVIImage(str(os.path.abspath(
            "../src/testImages/HySpex/220724_VNIR_Reflectance.img")))
        for key, value in image.meta:
            print(key, type(value), "\n- ", value)

        self.assertEqual("ENVI", image.meta.driver)
        self.assertEqual("float32", image.meta.dtype)
        self.assertEqual(2.0, image.meta.dataignore)
        self.assertEqual(808, image.meta.width)
        self.assertEqual(620, image.meta.height)
        self.assertEqual(200, image.meta.bandcount)


if __name__ == '__main__':
    unittest.main()
