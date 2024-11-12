import pyqtgraph as pg


class BandChangeImageItem(pg.ImageItem):
    """
    eventually might use this instead of image items to give the images themselves
    support for spectral images instead of handling it from the outside
    """
    def __init__(self):
        super().__init__(self)
