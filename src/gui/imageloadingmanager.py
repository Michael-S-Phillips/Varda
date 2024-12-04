import logging

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QObject

from src.models.imagemodel import ImageModel
import vardathreading

logger = logging.getLogger(__name__)


class ImageLoadingManager(QObject):
    
    sigImageLoaded = QtCore.pyqtSignal(ImageModel)
    
    def __init__(self, imageManager):
        super(ImageLoadingManager, self).__init__()
        self.imageManager = imageManager
        
    def openFileDialog(self):
        # TODO: automatically determine all file types that are supported
        fileName = QtWidgets.QFileDialog.getOpenFileName(None, 
                                                         "Open File", "",
                                                         "image file (*.hdr *.img "
                                                         "*.h5)")
        if fileName[0] is False:
            return
        
        self.loadImage(fileName[0])
        
    def loadImage(self, fileName):
        logger.info("Loading image: " + fileName)
        vardathreading.dispatchThreadProcess(self.sigImageLoaded.emit,
                                             self.imageManager.newImage, fileName)         