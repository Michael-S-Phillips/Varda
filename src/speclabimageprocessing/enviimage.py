from speclabimageprocessing.spectralimage import SpectralImage
import re


class ENVIImage(SpectralImage):
    image_type = "hdr"

    def __init__(self, file_path):
        super().__init__(file_path)
        print("HDR subclass Used")
