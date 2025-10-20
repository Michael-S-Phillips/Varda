from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QTabBar,
)
from PyQt6.QtCore import Qt


class DetachableTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(self.DetachableTabBar(self))
        self.detachedWindows = {}

    def detachTab(self, index):
        widget = self.widget(index)
        if widget is None:
            return

        label = self.tabText(index)
        self.removeTab(index)

        detachedTabWindow = self.DetachedTabWindow(label, widget, self)
        detachedTabWindow.show()

        self.detachedWindows[widget] = detachedTabWindow

    def reattachTab(self, widget, label):
        del self.detachedWindows[widget]
        self.addTab(widget, label)
        self.setCurrentWidget(widget)

    class DetachableTabBar(QTabBar):
        def __init__(self, parentTabWidget):
            super().__init__()
            self.parentTabWidget = parentTabWidget

        def mouseDoubleClickEvent(self, event):
            index = self.tabAt(event.pos())
            if index != -1:
                self.parentTabWidget.detachTab(index)
            super().mouseDoubleClickEvent(event)

    class DetachedTabWindow(QMainWindow):
        def __init__(self, label, widget, tab_widget):
            super().__init__()
            self.setWindowTitle(label)
            self.tabWidget = tab_widget
            self.label = label
            self.widget = widget
            self.newTabWidget = QTabWidget()
            self.setCentralWidget(self.newTabWidget)
            self.newTabWidget.addTab(self.widget, self.label)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        def closeEvent(self, event):
            # Reattach the widget back into the main tab widget
            self.tabWidget.reattachTab(self.widget, self.label)
            super().closeEvent(event)
