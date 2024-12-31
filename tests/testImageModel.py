"""
This file contains the test cases for the ImageModel class. 
It tests the initialization of the ImageManager class and the initialization of the 
inner models.
"""
# standard library
import unittest
import os
import logging
from datetime import datetime
from pathlib import Path

# third party imports
from PyQt6.QtCore import Qt
import numpy as np
import affine

# local imports
from models import ImageManager
from core.entities.image import TableModel
from core.entities.metadata import Metadata


def initLogging():
    """
    Setup logging. Logs will be saved in the "logs" directory. with a unique timestamp

    Usage: create a logger object in any file and use it to log messages, e.g.

      import logging
      logger = logging.getLogger(__name__)
      logger.debug("This is a debug message")
      logger.info("This is an info message")
      logger.warning("This is a warning message")
      logger.error("This is an error message")
    """

    logFolder = "UnitTestLogs"
    os.makedirs(logFolder, exist_ok=True)
    logTime = datetime.now().strftime('%Y-%m-%d_%I-%M-%S-%p')
    logName = Path(f"{logFolder}/UnitTest.log.{logTime}")
    logging.basicConfig(filename=logName, level=logging.DEBUG)

initLogging()

def initDummyImageData():
    dummyRasterData = np.random.rand(100, 100, 100)
    dummyMetadata = Metadata("ENVI", "float32", 1.1, 100, 100, 100,
                             {"r": 0, "g": 1, "b": 2}, affine.identity,
                             np.arange(100))
    return dummyRasterData, dummyMetadata

class TestImageModel(unittest.TestCase):
    """
    Thank copilot for writing these long tests
    """
    def setUp(self):
        self.dummyImageData = initDummyImageData()

    def test_initTableModel1(self):
        tableModel = TableModel(["r", "g", "b"], {"mono": [0, 0, 0],
                                                  "rgb": [0, 1, 2],
                                                  "custom1": [10, 20, 30]})
        self.assertIsNotNone(tableModel)
        self.assertEqual(tableModel.rowCount(), 3)
        self.assertEqual(tableModel.columnCount(), 3)
        self.assertEqual(tableModel.headerData(0, Qt.Orientation.Horizontal), "r")
        self.assertEqual(tableModel.headerData(1, Qt.Orientation.Horizontal), "g")
        self.assertEqual(tableModel.headerData(2, Qt.Orientation.Horizontal), "b")
        self.assertEqual(tableModel.headerData(0, Qt.Orientation.Vertical), "mono")
        self.assertEqual(tableModel.headerData(1, Qt.Orientation.Vertical), "rgb")
        self.assertEqual(tableModel.headerData(2, Qt.Orientation.Vertical), "custom1")
        self.assertEqual(tableModel.data(tableModel.index(0, 0)), 0)
        self.assertEqual(tableModel.data(tableModel.index(0, 1)), 0)
        self.assertEqual(tableModel.data(tableModel.index(0, 2)), 0)
        self.assertEqual(tableModel.data(tableModel.index(1, 0)), 0)
        self.assertEqual(tableModel.data(tableModel.index(1, 1)), 1)
        self.assertEqual(tableModel.data(tableModel.index(1, 2)), 2)
        self.assertEqual(tableModel.data(tableModel.index(2, 0)), 10)
        self.assertEqual(tableModel.data(tableModel.index(2, 1)), 20)
        self.assertEqual(tableModel.data(tableModel.index(2, 2)), 30)

    def test_initTableModel2(self):
        header = [f"col{i}" for i in range(11)]
        data = {f"row{j}": [i + j for i in range(11)] for j in range(11)}
        tableModel = TableModel(header, data)
        self.assertIsNotNone(tableModel)
        self.assertEqual(tableModel.rowCount(), 11)
        self.assertEqual(tableModel.columnCount(), 11)
        for i in range(11):
            self.assertEqual(tableModel.headerData(i, Qt.Orientation.Horizontal), f"col{i}")
            self.assertEqual(tableModel.headerData(i, Qt.Orientation.Vertical), f"row{i}")
            for j in range(11):
                self.assertEqual(tableModel.data(tableModel.index(i, j)), i + j)

    def test_editTableModel(self):
        tableModel = TableModel(["minR", "maxR", "minG", "maxG", "minB", "maxB"],
                                {"defaultfloat": [0, 1, 0, 1, 0, 1],
                                 "defaultuint8": [0, 255, 0, 255, 0, 255]})
        self.assertIsNotNone(tableModel)
        self.assertEqual(tableModel.rowCount(), 2)
        self.assertEqual(tableModel.columnCount(), 6)

        # Edit multiple cell values
        index1 = tableModel.index(0, 1)
        tableModel.setData(index1, 100)
        self.assertEqual(100, tableModel.data(index1))

        index2 = tableModel.index(1, 1)
        tableModel.setData(index2, 200)
        self.assertEqual(200, tableModel.data(index2))

        index3 = tableModel.index(1, 3)
        tableModel.setData(index3, 300)
        self.assertEqual(300, tableModel.data(index3))

        index4 = tableModel.index(1, 5)
        tableModel.setData(index4, 400)
        self.assertEqual(400, tableModel.data(index4))

        # Verify other cells remain unchanged
        self.assertEqual(0, tableModel.data(tableModel.index(0, 0)))
        self.assertEqual(0, tableModel.data(tableModel.index(0, 2)))
        self.assertEqual(1, tableModel.data(tableModel.index(0, 3)))
        self.assertEqual(0, tableModel.data(tableModel.index(0, 4)))
        self.assertEqual(1, tableModel.data(tableModel.index(0, 5)))
        self.assertEqual(0, tableModel.data(tableModel.index(1, 0)))
        self.assertEqual(0, tableModel.data(tableModel.index(1, 2)))
        self.assertEqual(0, tableModel.data(tableModel.index(1, 4)))

    def test_initImageModel(self):
        defaults = {"band": (["r", "g", "b"], {"mono": [0, 0, 0],
                                               "rgb": [0, 1, 2],
                                               "custom1": [10, 20, 30]}),
                    "stretch": (["min", "max"], {"standard": [0, 1],
                                                 "special1": [10, 100]}),
                    }

        imageModel = ImageModel(*self.dummyImageData, defaults=defaults)
        self.assertIsNotNone(imageModel)

        # Test other attributes
        self.assertTrue(isinstance(imageModel.rasterData, np.ndarray))
        self.assertEqual(imageModel.rasterData.shape, (100, 100, 100))
        self.assertTrue(isinstance(imageModel.metadata, Metadata))
        self.assertEqual(imageModel.metadata, self.dummyImageData[1])
        # Test metadata table
        self.assertIsNotNone(imageModel.metadataTable)
        self.assertEqual(9, imageModel.metadataTable.rowCount())
        self.assertEqual(1, imageModel.metadataTable.columnCount())

        # Test band table
        self.assertIsNotNone(imageModel.bandTable)
        self.assertEqual(3, imageModel.bandTable.rowCount())
        self.assertEqual(3, imageModel.bandTable.columnCount())
        self.assertEqual("r",
                         imageModel.bandTable.headerData(0, Qt.Orientation.Horizontal))
        self.assertEqual("g",
                         imageModel.bandTable.headerData(1, Qt.Orientation.Horizontal))
        self.assertEqual("b",
                         imageModel.bandTable.headerData(2, Qt.Orientation.Horizontal))
        self.assertEqual("mono",
                         imageModel.bandTable.headerData(0, Qt.Orientation.Vertical))
        self.assertEqual("rgb",
                         imageModel.bandTable.headerData(1, Qt.Orientation.Vertical))
        self.assertEqual("custom1",
                         imageModel.bandTable.headerData(2, Qt.Orientation.Vertical))
        self.assertEqual(0,
                         imageModel.bandTable.data(imageModel.bandTable.index(0, 0)))
        self.assertEqual(0,
                         imageModel.bandTable.data(imageModel.bandTable.index(0, 1)))
        self.assertEqual(0,
                         imageModel.bandTable.data(imageModel.bandTable.index(0, 2)))
        self.assertEqual(0,
                         imageModel.bandTable.data(imageModel.bandTable.index(1, 0)))
        self.assertEqual(1,
                         imageModel.bandTable.data(imageModel.bandTable.index(1, 1)))
        self.assertEqual(2,
                         imageModel.bandTable.data(imageModel.bandTable.index(1, 2)))
        self.assertEqual(10,
                         imageModel.bandTable.data(imageModel.bandTable.index(2, 0)))
        self.assertEqual(20,
                         imageModel.bandTable.data(imageModel.bandTable.index(2, 1)))
        self.assertEqual(30,
                         imageModel.bandTable.data(imageModel.bandTable.index(2, 2)))

        # Test stretch table
        self.assertIsNotNone(imageModel.stretchTable)
        self.assertEqual(2, imageModel.stretchTable.rowCount())
        self.assertEqual(2,  imageModel.stretchTable.columnCount())

        self.assertEqual("min", imageModel.stretchTable.headerData(0,
                                                                    Qt.Orientation.Horizontal))
        self.assertEqual("max", imageModel.stretchTable.headerData(1,
                                                                    Qt.Orientation.Horizontal))
        self.assertEqual("standard", imageModel.stretchTable.headerData(0,
                                                                         Qt.Orientation.Vertical))
        self.assertEqual("special1", imageModel.stretchTable.headerData(1,
                                                                        Qt.Orientation.Vertical))
        self.assertEqual(0, imageModel.stretchTable.data(
            imageModel.stretchTable.index(0, 0)))
        self.assertEqual(1, imageModel.stretchTable.data(
            imageModel.stretchTable.index(0, 1)))
        self.assertEqual(10, imageModel.stretchTable.data(
            imageModel.stretchTable.index(1, 0)))
        self.assertEqual(100, imageModel.stretchTable.data(
            imageModel.stretchTable.index(1, 1)))

        # Test ROI table
        self.assertIsNotNone(imageModel.ROITable)
        self.assertEqual(0, imageModel.ROITable.rowCount())
        self.assertEqual(0, imageModel.ROITable.columnCount())


    def test_initInnerModels1(self):
        defaults = {"band": (["r", "g", "b"], {"mono": [0, 0, 0],
                                               "rgb": [0, 1, 2],
                                               "custom1": [10, 20, 30]}),
                    "stretch": (["min", "max"], {"standard": [0, 1],
                                                 "special1": [10, 100]}),
                    }

        imageModel = ImageModel(*self.dummyImageData, defaults=defaults)
        self.assertIsNotNone(imageModel.metadataTable)
        self.assertIsNotNone(imageModel.bandTable)
        self.assertIsNotNone(imageModel.stretchTable)
        self.assertIsNotNone(imageModel.ROITable)

        self.assertEqual(9, imageModel.metadataTable.rowCount())
        self.assertEqual(1, imageModel.metadataTable.columnCount())

        self.assertEqual(3, imageModel.bandTable.rowCount())
        self.assertEqual(3, imageModel.bandTable.columnCount())

        self.assertEqual(2, imageModel.stretchTable.rowCount())
        self.assertEqual(2, imageModel.stretchTable.columnCount())

        self.assertEqual(0, imageModel.ROITable.rowCount())
        self.assertEqual(0, imageModel.ROITable.columnCount())


class TestImageManager(unittest.TestCase):
    def setUp(self):
        self.dummyImageData = initDummyImageData()

    def test_newENVIImage(self):
        manager = ImageManager()
        for i in range(3):
            model = manager.newImage(os.path.abspath(
                "../testImages/HySpex/220724_VNIR_Reflectance.img"))
            self.assertIsInstance(model.internalPointer(), ImageModel)
            self.assertEqual(manager.rowCount(), i + 1)
            self.assertEqual(model, manager.index(
                manager.rowCount()-1))

    def test_newHDF5Image(self):
        manager = ImageManager()
        for i in range(3):
            model = manager.newImage(os.path.abspath(
                "../testImages/NEON/NEON_D02_SERC_DP3_368000_4306000_reflectance.h5"))
            self.assertIsInstance(model.internalPointer(), ImageModel)
            self.assertEqual(manager.rowCount(), i + 1)
            self.assertEqual(model, manager.index(
                manager.rowCount()-1))

    def test_removeImage(self):
        manager = ImageManager()
        numImages = 3
        for i in range(numImages):
            model = manager.newImage(os.path.abspath(
                "../testImages/HySpex/220724_VNIR_Reflectance.img"))
            self.assertEqual(manager.rowCount(), i + 1)
        for i in range(numImages):
            manager.removeImage(0)
            self.assertEqual(manager.rowCount(), numImages - i - 1)

    def test_linkImages(self):
        model1 = self.manager.newImage(os.path.abspath(
            "../testImages/HySpex/220724_VNIR_Reflectance.img"))
        model2 = self.manager.newImage(os.path.abspath(
            "../testImages/HySpex/220724_VNIR_Reflectance.img"))
        self.manager.linkImages(model1, model2)
        self.assertEqual(len(self.manager.links), 1)

    def test_imageChanged(self):
        model = self.manager.newImage(os.path.abspath(
            "../testImages/HySpex/220724_VNIR_Reflectance.img"))
        model.sigImageChanged.emit()
        self.assertEqual(model.sigImageChanged, model.sigImageChanged)


from core.entities.image import ImageModel
from features.image_view_data.viewmodels.image_viewmodel import ImageViewModel

class TestImageViewSelectionModel(unittest.TestCase):

    def setUp(self):
        self.dummyImageData = initDummyImageData()
        self.imageModel = ImageModel(*self.dummyImageData)
        self.selectionModel = ImageViewModel(self.imageModel)

    def test_initial_band(self):
        self.assertEqual(self.selectionModel.getCurrentBand().r, 0)
        self.assertEqual(self.selectionModel.getCurrentBand().g, 0)
        self.assertEqual(self.selectionModel.getCurrentBand().b, 0)

    def test_initial_stretch(self):
        self.assertEqual(self.selectionModel.getCurrentStretch().minR, 0)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxR, 1)
        self.assertEqual(self.selectionModel.getCurrentStretch().minG, 0)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxG, 1)
        self.assertEqual(self.selectionModel.getCurrentStretch().minB, 0)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxB, 1)

    def test_select_band(self):
        self.selectionModel.selectBand(1)
        self.assertEqual(self.selectionModel.getCurrentBand().r, 0)
        self.assertEqual(self.selectionModel.getCurrentBand().g, 1)
        self.assertEqual(self.selectionModel.getCurrentBand().b, 2)

    def test_select_stretch(self):
        self.selectionModel.selectStretch(1)
        self.assertEqual(self.selectionModel.getCurrentStretch().minR, 0)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxR, 255)
        self.assertEqual(self.selectionModel.getCurrentStretch().minG, 0)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxG, 255)
        self.assertEqual(self.selectionModel.getCurrentStretch().minB, 0)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxB, 255)

    def test_set_band(self):
        self.selectionModel.setBandValues(5, 10, 15)
        self.assertEqual(self.selectionModel.getCurrentBand().r, 5)
        self.assertEqual(self.selectionModel.getCurrentBand().g, 10)
        self.assertEqual(self.selectionModel.getCurrentBand().b, 15)

    def test_set_stretch(self):
        self.selectionModel.setStretchValues(10, 20, 30, 40, 50, 60)
        self.assertEqual(self.selectionModel.getCurrentStretch().minR, 10)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxR, 20)
        self.assertEqual(self.selectionModel.getCurrentStretch().minG, 30)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxG, 40)
        self.assertEqual(self.selectionModel.getCurrentStretch().minB, 50)
        self.assertEqual(self.selectionModel.getCurrentStretch().maxB, 60)
