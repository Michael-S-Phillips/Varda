import unittest

from speclabimageprocessing import Metadata


class TestMetadata(unittest.TestCase):

    def testMetadata1(self):
        meta = Metadata("driver1", "dtype1", "dataignore1", "width1", "height1",
                        "bandcount1", "transform1", bonusMetadata="yoo imma bonus")
        for key, value in meta:
            print(key, "\n - ", value)
            pass

        print(meta._dtype)
        print(meta.bonusMetadata)



if __name__ == '__main__':
    unittest.main()
