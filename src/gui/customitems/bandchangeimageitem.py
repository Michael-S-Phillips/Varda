import pyqtgraph as pg


class BandChangeImageItem(pg.ImageItem):
    """
    eventually might use this instead of image items to give the imageitems themselves
    support for spectral images instead of handling it outside of it
    """
    def __init__(self):
        super().__init__(self)
