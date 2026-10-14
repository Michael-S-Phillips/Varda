"""Draw on Image in the scene: shapes come back as the pixels inside them."""

import numpy as np
from affine import Affine
from rasterio.crs import CRS
from shapely.geometry import Polygon

from varda.common.entities import ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.raster_view.viewport_tools.roi_tools import ROIDrawTool
from varda.workspaces.spectral_hourglass.scene_view import SceneView


def test_a_shape_on_a_georeferenced_image_selects_the_pixels_under_it(qtbot):
    transform = Affine(18.0, 0.0, 1000.0, 0.0, -18.0, 5000.0)  # 18 m pixels
    source = ArrayDataSource(
        np.random.default_rng(0).uniform(0.1, 0.5, (10, 12, 3)).astype(np.float32),
        transform=transform,
        crs=CRS.from_epsg(32612),
    )
    scene = SceneView(VardaRaster(source, name="map"))
    qtbot.addWidget(scene)
    drawn = []
    scene.sigPixelsDrawn.connect(
        lambda pixels, add: drawn.append((set(pixels.tolist()), add))
    )
    scene.toolManager.activateTool(ROIDrawTool)
    tool = scene.toolManager.activeTool
    assert isinstance(tool, ROIDrawTool)
    # pixel columns 2..4, rows 1..2, given in map coordinates as the tool does
    corners = [transform * (c, r) for c, r in [(2, 1), (5, 1), (5, 3), (2, 3)]]
    tool.sigROIDrawingComplete.emit(
        {"geometry": Polygon(corners), "roiType": ROIMode.RECTANGLE}
    )
    assert drawn == [({r * 12 + c for r in (1, 2) for c in (2, 3, 4)}, True)]
