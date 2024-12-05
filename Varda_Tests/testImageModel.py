"""
This file contains the test cases for the ImageModel class. 
It tests the initialization of the ImageManager class and the initialization of the 
inner models.
"""
# standard library
import unittest
import sys
import os

# third party imports
from PyQt6.QtWidgets import QApplication, QTreeView, QTableView
from PyQt6.QtCore import Qt
import numpy as np
import affine

# local imports
from models import ImageManager
# from imageloaders.enviimageloader import ENVIImageLoader
# from imageloaders.hdf5imageloader import HDF5ImageLoader
from gui.customwidgets.imagerasterdataviewer import ImageRasterDataViewer
from models.imagemodel import ImageModel
from models.imagemodel import TableModel
from models.metadata import Metadata


class TestImageModel(unittest.TestCase):
    """
    Thank copilot for writing these long tests
    """
    def setUp(self):
        # self.enviLoader = ENVIImageLoader()
        # self.hdf5Loader = HDF5ImageLoader()

        dummyMetadata = Metadata("ENVI", "float32", 1.1, 100, 100, 100,
                                 {"r": 0, "g": 1, "b": 2}, affine.identity,
                                 np.arange(100))
        self.dummyImageData = (np.random.rand(100, 100, 100), dummyMetadata)

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
        dummyMetadata = Metadata("ENVI", "float32", 1.1, 100, 100, 100,
                                 {"r": 0, "g": 1, "b": 2}, affine.identity,
                                 np.arange(100))
        self.dummyImageData = (np.random.rand(100, 100, 100), dummyMetadata)

    def test_newENVIImage(self):
        manager = ImageManager()
        for i in range(3):
            model = manager.newImage(os.path.abspath(
                "../src/testImages/HySpex/220724_VNIR_Reflectance.img"))
            self.assertIsInstance(model.internalPointer(), ImageModel)
            self.assertEqual(manager.rowCount(), i + 1)
            self.assertEqual(model, manager.index(
                manager.rowCount()-1))

    def test_newHDF5Image(self):
        manager = ImageManager()
        for i in range(3):
            model = manager.newImage(os.path.abspath(
                "../src/testImages/NEON/NEON_D02_SERC_DP3_368000_4306000_reflectance.h5"))
            self.assertIsInstance(model.internalPointer(), ImageModel)
            self.assertEqual(manager.rowCount(), i + 1)
            self.assertEqual(model, manager.index(
                manager.rowCount()-1))

    def test_removeImage(self):
        manager = ImageManager()
        numImages = 3
        for i in range(numImages):
            model = manager.newImage(os.path.abspath(
                "../src/testImages/HySpex/220724_VNIR_Reflectance.img"))
            self.assertEqual(manager.rowCount(), i + 1)
        for i in range(numImages):
            manager.removeImage(0)
            self.assertEqual(manager.rowCount(), numImages - i - 1)

    def test_linkImages(self):
        model1 = self.manager.newImage(os.path.abspath(
            "../src/testImages/HySpex/220724_VNIR_Reflectance.img"))
        model2 = self.manager.newImage(os.path.abspath(
            "../src/testImages/HySpex/220724_VNIR_Reflectance.img"))
        self.manager.linkImages(model1, model2)
        self.assertEqual(len(self.manager.links), 1)

    def test_imageChanged(self):
        model = self.manager.newImage(os.path.abspath(
            "../src/testImages/HySpex/220724_VNIR_Reflectance.img"))
        model.sigImageChanged.emit()
        self.assertEqual(model.sigImageChanged, model.sigImageChanged)
