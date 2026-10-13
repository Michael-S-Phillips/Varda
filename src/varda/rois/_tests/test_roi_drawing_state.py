"""What the next drawn ROI becomes: its shape and its class."""

from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.common.palette import CLASS_PALETTE
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_drawing_state import ROIDrawingState


def _state() -> tuple[ROICollection, ROIDrawingState]:
    rois = ROICollection()
    return rois, ROIDrawingState(rois)


def _hex(color: Color) -> str:
    return color.toQColor().name()


def test_the_default_shape_is_freehand_and_changes_are_announced():
    _, state = _state()
    seen = []
    state.sigShapeChanged.connect(seen.append)
    assert state.shape == ROIMode.FREEHAND
    state.setShape(ROIMode.POLYGON)
    assert state.shape == ROIMode.POLYGON and seen == [ROIMode.POLYGON]


def test_the_first_shape_starts_a_class_and_later_shapes_join_it():
    rois, state = _state()
    first = state.addDrawnShape(box(0, 0, 2, 2), ROIMode.FREEHAND)
    second = state.addDrawnShape(box(4, 4, 6, 6), ROIMode.RECTANGLE)
    assert state.activeClass == "Class 1"
    assert rois.classes() == {"Class 1": [first, second]}
    assert rois.getROI(first).color == rois.getROI(second).color
    assert _hex(rois.getROI(first).color) == CLASS_PALETTE[0]
    assert rois.getROI(second).roiType == ROIMode.RECTANGLE


def test_a_new_class_gets_a_fresh_name_and_colour_and_takes_the_next_shapes():
    rois, state = _state()
    state.addDrawnShape(box(0, 0, 2, 2), ROIMode.FREEHAND)
    seen = []
    state.sigActiveClassChanged.connect(seen.append)
    name = state.newClass()
    assert name == "Class 2" and state.activeClass == "Class 2" and seen == ["Class 2"]
    assert [(c.name, c.count) for c in state.classes()] == [
        ("Class 1", 1),
        ("Class 2", 0),
    ]
    fid = state.addDrawnShape(box(4, 4, 6, 6), ROIMode.FREEHAND)
    assert rois.getROI(fid).name == "Class 2"
    assert _hex(rois.getROI(fid).color) == CLASS_PALETTE[1]


def test_choosing_an_existing_class_adds_to_it_in_its_own_colour():
    rois, state = _state()
    custom = Color(0.2, 0.4, 0.6, 0.5)
    rois.addROI(box(0, 0, 2, 2), "basalt", custom, ROIMode.POLYGON)
    state.newClass()
    state.setActiveClass("basalt")
    fid = state.addDrawnShape(box(4, 4, 6, 6), ROIMode.FREEHAND)
    assert rois.getROI(fid).name == "basalt" and rois.getROI(fid).color == custom


def test_new_classes_avoid_names_and_colours_already_in_use():
    rois, state = _state()
    rois.addROI(
        box(0, 0, 2, 2),
        "Class 1",
        Color.fromHexString(CLASS_PALETTE[0] + "80"),
        ROIMode.POLYGON,
    )
    rois.addROI(
        box(0, 0, 2, 2),
        "Class 2",
        Color.fromHexString(CLASS_PALETTE[1] + "80"),
        ROIMode.POLYGON,
    )
    name = state.newClass()
    fid = state.addDrawnShape(box(4, 4, 6, 6), ROIMode.FREEHAND)
    assert name == "Class 3"
    assert _hex(rois.getROI(fid).color) == CLASS_PALETTE[2]


def test_the_active_class_survives_deleting_its_last_roi():
    rois, state = _state()
    fid = state.addDrawnShape(box(0, 0, 2, 2), ROIMode.FREEHAND)
    rois.removeROI(fid)
    assert state.activeClass == "Class 1"
    assert [(c.name, c.count) for c in state.classes()] == [("Class 1", 0)]


def test_collection_changes_are_announced_as_class_changes():
    rois, state = _state()
    seen = []
    state.sigClassesChanged.connect(lambda: seen.append(True))
    rois.addROI(box(0, 0, 2, 2), "basalt", Color.black(), ROIMode.POLYGON)
    assert seen
