"""Sessions: the open images, the workspaces showing them, and their ROIs, as a
JSON ``.varda`` file.

Only images that live in a file can be saved (the session stores paths, not
pixels); in-memory results such as analysis outputs have to be exported first
and are reported back to the caller instead.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import attrs
from shapely.geometry import mapping, shape

from varda.common.entities import Color, ROIMode, VardaRaster
from varda.rois.roi_collection import ROICollection
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
)
from varda.workspaces.general_image_analysis import GeneralImageAnalysisWorkflow

SESSION_SUFFIX = ".varda"
SESSION_FILE_FILTER = "Varda session (*.varda)"
_FORMAT = "varda-session"
_VERSION = 1


@attrs.frozen
class WorkspaceState:
    kind: str  # "general" or "dual"
    images: tuple[str, ...] = attrs.field(
        converter=tuple
    )  # (image,) or (primary, secondary)
    rois: dict = attrs.field(factory=dict)  # GeoJSON FeatureCollection, see roisToJson


@attrs.frozen
class SessionState:
    images: tuple[str, ...] = attrs.field(converter=tuple)  # file paths in list order
    workspaces: tuple[WorkspaceState, ...] = attrs.field(converter=tuple)


@attrs.frozen
class SessionCapture:
    state: SessionState
    # names of images that exist only in memory and were left out
    unsavedImages: tuple[str, ...]


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
        roiTypeName = properties.pop("roi_type", ROIMode.POLYGON.name)
        roiType = (
            ROIMode[roiTypeName]
            if roiTypeName in ROIMode.__members__
            else ROIMode.POLYGON
        )
        collection.addROI(
            shape(feature["geometry"]), name, color, roiType, **properties
        )


def captureSession(
    images: Sequence[VardaRaster], workspaces: Iterable[object]
) -> SessionCapture:
    """Describe the project: every file-backed image and every workspace whose
    images are all file-backed."""
    pathOf: dict[int, str] = {}
    unsaved = []
    for image in images:
        if image.filePath:
            pathOf[id(image)] = image.filePath
        else:
            unsaved.append(image.name)

    states = []
    for workspace in workspaces:
        described = _describe(workspace)
        if described is None:
            continue
        kind, shown = described
        if any(id(image) not in pathOf for image in shown):
            continue
        states.append(
            WorkspaceState(
                kind,
                tuple(pathOf[id(image)] for image in shown),
                roisToJson(getattr(workspace, "roiCollection")),
            )
        )
    return SessionCapture(
        SessionState(tuple(pathOf.values()), tuple(states)), tuple(unsaved)
    )


def _describe(workspace: object) -> tuple[str, list[VardaRaster]] | None:
    if isinstance(workspace, GeneralImageAnalysisWorkflow):
        return "general", [workspace.config.image.get()]
    if isinstance(workspace, DualImageWorkspace):
        return "dual", [workspace.image1, workspace.image2]
    return None


def writeSession(state: SessionState, path: str | Path) -> Path:
    """Write the session as JSON; the ``.varda`` suffix is added if missing."""
    target = Path(path)
    if target.suffix != SESSION_SUFFIX:
        target = target.with_suffix(SESSION_SUFFIX)
    document = {
        "format": _FORMAT,
        "version": _VERSION,
        "images": list(state.images),
        "workspaces": [attrs.asdict(workspace) for workspace in state.workspaces],
    }
    target.write_text(json.dumps(document, indent=2))
    return target


def readSession(path: str | Path) -> SessionState:
    document = json.loads(Path(path).read_text())
    if not isinstance(document, dict) or document.get("format") != _FORMAT:
        raise ValueError(f"{path} is not a Varda session file.")
    return SessionState(
        tuple(document["images"]),
        tuple(
            WorkspaceState(entry["kind"], tuple(entry["images"]), entry["rois"])
            for entry in document["workspaces"]
        ),
    )
