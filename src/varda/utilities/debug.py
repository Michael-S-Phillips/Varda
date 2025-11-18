import time

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QLineEdit,
)
from PyQt6.QtCore import Qt
import numpy as np

from varda.common.entities import Metadata, Image, Band

DEBUG = True


class Profiler:  # pylint: disable=too-few-public-methods
    """
    A simple profiler to measure the time elapsed between two points in the code.

    Usage:
        profiler = Profiler()
        # Code to be profiled
        profiler("Part 1 elapsed") # Output - Part 1 time elapsed: 0.1234 ms
        # More code to be profiled
        profiler("Part 2 time elapsed") # Output - Part 2 time elapsed: 0.1234 ms
    """

    # Set this flag to True to disable the profiler
    DISABLE = False  # pylint: disable=invalid-name

    def __init__(self):
        """
        Initialize the profiler with the current time.
        """
        self.timeStarted = time.perf_counter()

    def __call__(self, *args):
        """
        Measure and print the time elapsed since the last call or initialization.

        If the DISABLE flag is set to True, the function will return without doing
        anything.

        @param:
            *args: Optional positional arguments. If provided, the first argument
            will be used as the message prefix.
        """
        if self.DISABLE:
            return
        timeElapsed = (time.perf_counter() - self.timeStarted) * 1000
        if len(args) > 0:
            print(f"{args[0]}: {timeElapsed: 0.4f} ms")
        else:
            print(f"Time elapsed: {timeElapsed: 0.4f} ms")
        self.timeStarted = time.perf_counter()


class ProjectContextDataTable(QWidget):
    """A debugging widget for displaying all project context data."""

    def __init__(self, proj, parent=None):
        super().__init__(parent)
        self.projectContext = proj
        self._initUI()
        self._connectSignals()
        self.show()

    def _initUI(self):
        self.setWindowTitle("Project Context Data")
        self.setWindowTitle("Project Context Data")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.layout = QVBoxLayout(self)

        self.searchBox = QLineEdit(self)
        self.searchBox.setPlaceholderText("Search...")
        self.searchBox.textChanged.connect(self.filterTree)
        self.layout.addWidget(self.searchBox)

        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setColumnCount(2)
        self.layout.addWidget(self.treeWidget)
        self.setLayout(self.layout)
        self.updateData()

    def _connectSignals(self):
        self.projectContext.sigDataChanged.connect(self.updateData)

    def updateData(self, changeType=None):
        """Update the tree widget with the current project context data."""
        self.treeWidget.clear()
        data = self.projectContext._projectData.serialize()
        self._populateTree(data, self.treeWidget.invisibleRootItem())

    def _populateTree(self, data, parent):
        """Recursively populate the tree widget with data."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    item = QTreeWidgetItem([key])
                    parent.addChild(item)
                    self._populateTree(value, item)
                else:
                    item = QTreeWidgetItem([key, str(value)])
                    parent.addChild(item)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                if isinstance(value, (dict, list)):
                    item = QTreeWidgetItem([str(index)])
                    parent.addChild(item)
                    self._populateTree(value, item)
                else:
                    item = QTreeWidgetItem([f"{index} ({type(value)})", str(value)])
                    parent.addChild(item)

    def filterTree(self, text):
        """Filter the tree widget items based on the search text."""
        for i in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(i)
            self._filterItem(item, text)

    def _filterItem(self, item, text):
        """Recursively filter the tree widget items."""
        match = (
            text.lower() in item.text(0).lower() or text.lower() in item.text(1).lower()
        )
        for i in range(item.childCount()):
            child = item.child(i)
            childMatch = self._filterItem(child, text)
            match = match or childMatch
        item.setHidden(not match)
        item.setExpanded(match)
        return match


def loadRandomImageIntoProject(app, shape=(100, 100, 100), res=(10, 10, 10)):
    """Load a random Image entity into the specified project."""
    image = generate_random_image(shape, res)
    app.images.append(image)


randomImageNo = 0


def generate_random_image(shape=(100, 100, 100), res=(10, 10, 10)):
    """Generate a random Image entity of the specified size."""
    global randomImageNo
    import numpy as np

    raster = generate_perlin_noise_3d(shape, res)
    metadata = Metadata(
        name=f"random image {randomImageNo}",
        wavelengths=np.array(
            ["wavelength " + num for num in map(str, range(shape[2]))]
        ),
        defaultBand=[0, 0, 0],
    )
    randomImageNo += 1
    return Image(raster, metadata)


### credit: https://github.com/pvigier/perlin-numpy/blob/master/perlin_numpy
def generate_perlin_noise_3d(shape, res, seed=None, tileable=(False, False, False)):
    """Generate a 3D numpy array of perlin noise.

    Args:
        shape: The shape of the generated array (tuple of three ints).
            This must be a multiple of res.
        res: The number of periods of noise to generate along each
            axis (tuple of three ints). Note shape must be a multiple
            of res.
        tileable: If the noise should be tileable along each axis
            (tuple of three bools). Defaults to (False, False, False).
        interpolant: The interpolation function, defaults to
            t*t*t*(t*(t*6 - 15) + 10).

    Returns:
        A numpy array of shape shape with the generated noise.

    Raises:
        ValueError: If shape is not a multiple of res.
    """
    if seed is not None:
        np.random.seed(seed)

    def f(t):
        return 6 * t**5 - 15 * t**4 + 10 * t**3

    delta = (res[0] / shape[0], res[1] / shape[1], res[2] / shape[2])
    d = (shape[0] // res[0], shape[1] // res[1], shape[2] // res[2])
    grid = np.mgrid[0 : res[0] : delta[0], 0 : res[1] : delta[1], 0 : res[2] : delta[2]]
    grid = grid.transpose(1, 2, 3, 0) % 1
    # Gradients
    theta = 2 * np.pi * np.random.rand(res[0] + 1, res[1] + 1, res[2] + 1)
    phi = 2 * np.pi * np.random.rand(res[0] + 1, res[1] + 1, res[2] + 1)
    gradients = np.stack(
        (np.sin(phi) * np.cos(theta), np.sin(phi) * np.sin(theta), np.cos(phi)), axis=3
    )
    if tileable[0]:
        gradients[-1, :, :] = gradients[0, :, :]
    if tileable[1]:
        gradients[:, -1, :] = gradients[:, 0, :]
    if tileable[2]:
        gradients[:, :, -1] = gradients[:, :, 0]
    gradients = gradients.repeat(d[0], 0).repeat(d[1], 1).repeat(d[2], 2)
    g000 = gradients[: -d[0], : -d[1], : -d[2]]
    g100 = gradients[d[0] :, : -d[1], : -d[2]]
    g010 = gradients[: -d[0], d[1] :, : -d[2]]
    g110 = gradients[d[0] :, d[1] :, : -d[2]]
    g001 = gradients[: -d[0], : -d[1], d[2] :]
    g101 = gradients[d[0] :, : -d[1], d[2] :]
    g011 = gradients[: -d[0], d[1] :, d[2] :]
    g111 = gradients[d[0] :, d[1] :, d[2] :]
    # Ramps
    n000 = np.sum(
        np.stack((grid[:, :, :, 0], grid[:, :, :, 1], grid[:, :, :, 2]), axis=3) * g000,
        3,
    )
    n100 = np.sum(
        np.stack((grid[:, :, :, 0] - 1, grid[:, :, :, 1], grid[:, :, :, 2]), axis=3)
        * g100,
        3,
    )
    n010 = np.sum(
        np.stack((grid[:, :, :, 0], grid[:, :, :, 1] - 1, grid[:, :, :, 2]), axis=3)
        * g010,
        3,
    )
    n110 = np.sum(
        np.stack((grid[:, :, :, 0] - 1, grid[:, :, :, 1] - 1, grid[:, :, :, 2]), axis=3)
        * g110,
        3,
    )
    n001 = np.sum(
        np.stack((grid[:, :, :, 0], grid[:, :, :, 1], grid[:, :, :, 2] - 1), axis=3)
        * g001,
        3,
    )
    n101 = np.sum(
        np.stack((grid[:, :, :, 0] - 1, grid[:, :, :, 1], grid[:, :, :, 2] - 1), axis=3)
        * g101,
        3,
    )
    n011 = np.sum(
        np.stack((grid[:, :, :, 0], grid[:, :, :, 1] - 1, grid[:, :, :, 2] - 1), axis=3)
        * g011,
        3,
    )
    n111 = np.sum(
        np.stack(
            (grid[:, :, :, 0] - 1, grid[:, :, :, 1] - 1, grid[:, :, :, 2] - 1), axis=3
        )
        * g111,
        3,
    )
    # Interpolation
    t = f(grid)
    n00 = n000 * (1 - t[:, :, :, 0]) + t[:, :, :, 0] * n100
    n10 = n010 * (1 - t[:, :, :, 0]) + t[:, :, :, 0] * n110
    n01 = n001 * (1 - t[:, :, :, 0]) + t[:, :, :, 0] * n101
    n11 = n011 * (1 - t[:, :, :, 0]) + t[:, :, :, 0] * n111
    n0 = (1 - t[:, :, :, 1]) * n00 + t[:, :, :, 1] * n10
    n1 = (1 - t[:, :, :, 1]) * n01 + t[:, :, :, 1] * n11
    return (1 - t[:, :, :, 2]) * n0 + t[:, :, :, 2] * n1
