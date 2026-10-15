"""The Ames Stereo Pipeline entry in Optional Features, and Auto Align's use
of it."""

import platform
from pathlib import Path

import pytest

from varda.mosaicking.backends.asp import AspInstall
from varda.mosaicking.matching import MatchMethod
from varda.optional_features import asp_section
from varda.mosaicking.backends._tests.test_asp import _stripsProject
from varda.optional_features.asp_section import AspSection
from varda.workspaces.mosaic.auto_align_dialog import AutoAlignDialog


@pytest.fixture
def found(monkeypatch):
    """Replace detection; returns a setter for what it finds."""
    result: dict = {"install": None}
    monkeypatch.setattr(
        asp_section, "findAsp", lambda *args, **kwargs: result["install"]
    )
    asp_section._cache.clear()

    def find(install):
        result["install"] = install
        asp_section._cache.clear()  # as Optional Features re-detects

    yield find
    asp_section._cache.clear()


@pytest.mark.skipif(platform.system() == "Windows", reason="no ASP on Windows")
def test_nothing_found_offers_the_download(qtbot, found):
    section = AspSection()
    qtbot.addWidget(section)
    assert section.status.text() == "Not found."
    assert section.downloadButton.isEnabled() == (section.release is not None)
    assert not section.removeButton.isVisibleTo(section)


@pytest.mark.skipif(platform.system() == "Windows", reason="no ASP on Windows")
def test_an_existing_install_is_shown_and_never_removed(qtbot, found):
    found(AspInstall(Path("/opt/asp/bin"), "3.3.0", "conda environment asp"))
    section = AspSection()
    qtbot.addWidget(section)
    assert (
        "3.3.0" in section.status.text()
        and "conda environment asp" in section.status.text()
    )
    assert not section.downloadButton.isEnabled()
    assert not section.removeButton.isVisibleTo(section)
    found(AspInstall(Path("/x/StereoPipeline-3.7.0/bin"), "3.7.0", "Varda download"))
    section.refresh(redetect=True)
    assert section.removeButton.isVisibleTo(section)


def _dialog(qtbot):
    project = _stripsProject()
    dialog = AutoAlignDialog(project, 1)
    qtbot.addWidget(dialog)
    return dialog


def test_auto_align_offers_asp_only_when_found(qtbot, found):
    first = _dialog(qtbot)
    assert (
        not first.method.model()
        .item(list(MatchMethod).index(MatchMethod.ASP))
        .isEnabled()
    )
    install = AspInstall(Path("/opt/asp/bin"), "3.3.0", "conda environment asp")
    found(install)
    dialog = _dialog(qtbot)
    assert (
        dialog.method.model().item(list(MatchMethod).index(MatchMethod.ASP)).isEnabled()
    )
    dialog.method.setCurrentIndex(dialog.method.findData(MatchMethod.ASP))
    assert dialog.settings().asp == install
