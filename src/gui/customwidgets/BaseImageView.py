from PyQt6.QtWidgets import QWidget


class BaseImageView(QWidget):

    def __init__(self, imageModel=None, parent=None):
        super().__init__(parent)

        self.imageModel = imageModel


        self.__initUI()



    def __initUI(self):
        pass

    @property
    def imageModel(self):
        return self.__imageModel

    @imageModel.setter
    def imageModel(self, value):
        self.__imageModel = value
        self.__imageModelChanged()


    def __imageModelChanged(self):
        pass

    def __updateView(self):
        pass

    def __updateModel(self):
        pass
