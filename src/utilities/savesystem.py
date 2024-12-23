"""
This module contains the save system for Varda.
To start, we will only save the ImageManager.
Eventually, we would like to save the state of all the widgets, so they can be
reopened automatically.
"""

from PyQt6.QtCore import QFile, QIODevice, QDataStream


def saveProject(imageManager, filePath):
    """
    Save the image manager to the save file.
    """
    file = QFile(filePath)
    file.open(QIODevice.OpenModeFlag.WriteOnly)
    out = QDataStream(file)

    imageManager.save(out)
    file.close()

def loadProject(imageManager, filePath):
    """
    Load the image manager from the load file.
    """
    file = QFile(filePath)
    file.open(QIODevice.OpenModeFlag.ReadOnly)
    inStream = QDataStream(file)

    imageManager.load(inStream)
    file.close()
