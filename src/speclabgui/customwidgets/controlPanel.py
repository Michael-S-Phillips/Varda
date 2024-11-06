from PyQt6 import QtCore, QtWidgets


class ControlPanel(QtWidgets.QWidget):
    """
    Control panel for launching different components like the frequency plot,
    RGB histograms, and other features.
    """

    def __init__(self, parent=None):
        super(ControlPanel, self).__init__(parent)

        # Main layout for the control panel
        layout = QtWidgets.QVBoxLayout()

        # Create a list widget
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.addItem("Frequency Plot")
        self.list_widget.addItem("Red Histogram")
        self.list_widget.addItem("Green Histogram")
        self.list_widget.addItem("Blue Histogram")
        self.list_widget.addItem("Band Math")
        self.list_widget.addItem("Scatter Plot")

        layout.addWidget(self.list_widget)

        # Connect the list item click to the function
        self.list_widget.itemClicked.connect(self.launch_component)

        # Set layout for the control panel
        self.setLayout(layout)

    def launch_component(self, item):
        """
        Launches the component based on the clicked item in the list.
        """
        component_name = item.text()

        if component_name == "Frequency Plot":
            self.launch_frequency_plot()
        elif component_name == "Red Histogram":
            self.launch_histogram('Red')
        elif component_name == "Green Histogram":
            self.launch_histogram('Green')
        elif component_name == "Blue Histogram":
            self.launch_histogram('Blue')
        elif component_name == "Band Math":
            self.launch_band_math()
        elif component_name == "Scatter Plot":
            self.launch_scatter_plot()

    def launch_frequency_plot(self):
        QtWidgets.QMessageBox.information(self, "Launch", "Frequency Plot launched!")

    def launch_histogram(self, color):
        QtWidgets.QMessageBox.information(self, "Launch", f"{color} Histogram launched!")

    def launch_band_math(self):
        QtWidgets.QMessageBox.information(self, "Launch", "Band Math launched!")

    def launch_scatter_plot(self):
        QtWidgets.QMessageBox.information(self, "Launch", "Scatter Plot launched!")
