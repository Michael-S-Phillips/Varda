"""ROIs can be hidden and shown; hidden ones stay in the collection."""

from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_json import roisFromJson, roisToJson

RED = Color(1.0, 0.0, 0.0, 0.5)


def _collection(count: int = 3) -> tuple[ROICollection, list[int]]:
    collection = ROICollection()
    fids = [
        collection.addROI(box(i, i, i + 2, i + 2), f"r{i}", RED, ROIMode.RECTANGLE)
        for i in range(count)
    ]
    return collection, fids


def test_new_rois_are_visible_and_can_be_hidden():
    collection, (a, b, _c) = _collection()
    changed = []
    collection.sigVisibilityChanged.connect(changed.append)
    assert collection.isVisible(a)
    collection.setVisible(a, False)
    assert not collection.isVisible(a) and collection.isVisible(b)
    assert changed == [a]
    collection.setVisible(a, False)  # no change, no signal
    assert changed == [a]
    assert len(collection) == 3  # hidden, not removed


def test_all_or_only_one_can_be_shown():
    collection, (a, b, c) = _collection()
    collection.setAllVisible(False)
    assert not any(collection.isVisible(f) for f in (a, b, c))
    collection.showOnly(b)
    assert [collection.isVisible(f) for f in (a, b, c)] == [False, True, False]
    collection.setAllVisible(True)
    assert all(collection.isVisible(f) for f in (a, b, c))


def test_removing_a_hidden_roi_forgets_it():
    collection, (a, _b, _c) = _collection()
    collection.setVisible(a, False)
    collection.removeROI(a)
    assert collection.hiddenFids() == set()


def test_sessions_keep_which_rois_are_hidden():
    collection, (a, b, _c) = _collection()
    collection.setVisible(b, False)
    restored = ROICollection()
    roisFromJson(roisToJson(collection), restored)
    visible = [restored.isVisible(roi.fid) for roi in restored.getAllROIs()]
    assert visible == [True, False, True]
    assert "visible" not in restored.getROI(restored.fids[0]).properties
