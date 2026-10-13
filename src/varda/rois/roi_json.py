"""ROIs as GeoJSON: how sessions store them and how duplicated workspaces
copy them."""

from __future__ import annotations

import json

from shapely.geometry import mapping, shape

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection


def roisToJson(collection: ROICollection) -> dict:
    """A GeoJSON FeatureCollection (plain JSON types) of the collection's ROIs,
    with Varda's name/color/roi_type and any user columns as properties."""
    features = [
        {
            "type": "Feature",
            "geometry": mapping(roi.geometry),
            "properties": {
                "name": roi.name,
                "color": roi.color.toHexString(),
                "roi_type": roi.roiType.name,
                **roi.properties,
                **({} if collection.isVisible(roi.fid) else {"visible": False}),
            },
        }
        for roi in collection.getAllROIs()
    ]
    data = {
        "type": "FeatureCollection",
        "features": features,
        "crs": collection.crs.to_wkt() if collection.crs is not None else None,
    }
    return json.loads(json.dumps(data, default=str))


def roisFromJson(data: dict, collection: ROICollection) -> None:
    """Add the ROIs of a ``roisToJson`` document to ``collection``."""
    for feature in data.get("features", []):
        properties = dict(feature.get("properties", {}))
        name = properties.pop("name", "ROI")
        color = Color.fromHexString(properties.pop("color", "#ff000080"))
        visible = bool(properties.pop("visible", True))
        roiTypeName = properties.pop("roi_type", ROIMode.POLYGON.name)
        roiType = (
            ROIMode[roiTypeName]
            if roiTypeName in ROIMode.__members__
            else ROIMode.POLYGON
        )
        fid = collection.addROI(
            shape(feature["geometry"]), name, color, roiType, **properties
        )
        if not visible:
            collection.setVisible(fid, False)
