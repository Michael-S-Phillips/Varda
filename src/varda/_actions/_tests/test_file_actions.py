"""Importing images by path goes through the same loading pipeline as the dialog."""

from varda._actions import _file_actions
from varda.common.di_types import ProjectImages


def test_import_image_paths_loads_each_file_into_the_project(monkeypatch):
    calls = []
    monkeypatch.setattr(
        _file_actions.ImageLoadingService,
        "load_images",
        classmethod(lambda cls, **kwargs: calls.append(kwargs)),
    )
    images = ProjectImages()

    _file_actions.importImagePaths(["/data/a.img", "/data/b.tif"], images)

    (call,) = calls
    assert call["file_paths"] == ["/data/a.img", "/data/b.tif"]
    assert call["on_success_callback"] == images.append
