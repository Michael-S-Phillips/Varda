"""The download list: essential files come checked, the total shows, and the
queue downloads into one folder per product, opens the data and exports."""

import csv
import functools
import http.server
import threading
from pathlib import Path

import pytest
import shapely
from PyQt6.QtCore import QSettings, Qt

from varda.catalogs.catalog import Catalog, Product, RemoteFile
from varda.workspaces.find_data.downloads_panel import (
    DONE,
    FOLDER_KEY,
    WAITING,
    DownloadsPanel,
    openableFiles,
)

FILES = {
    "obs.hdr": b"ENVI\n" * 20,
    "obs.img": b"\0" * 5000,
    "obs_browse.png": b"P" * 300,
}
PRODUCT = Product("obs", "An observation", "mars_obs", shapely.box(0, 0, 1, 1))


@pytest.fixture
def server(tmp_path):
    served = tmp_path / "served"
    served.mkdir()
    for name, data in FILES.items():
        (served / name).write_bytes(data)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=served)
    handler.log_message = lambda *args: None  # type: ignore[attr-defined]
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def catalog(server):
    class Archive(Catalog):
        catalogId = "archive"
        name = "Archive"

        def files(self, product):
            def remote(name, role, essential):
                return RemoteFile(
                    name,
                    f"{server}/{name}",
                    len(FILES[name]),
                    role=role,
                    essential=essential,
                )

            return [
                remote("obs_browse.png", "browse", False),
                remote("obs.hdr", "data", True),
                remote("obs.img", "data", True),
            ]

    return Archive()


@pytest.fixture
def panel(qtbot, tmp_path):
    QSettings().setValue(FOLDER_KEY, str(tmp_path / "downloads"))
    widget = DownloadsPanel()
    qtbot.addWidget(widget)
    return widget


def _listed(panel, catalog, qtbot):
    panel.add(catalog, [PRODUCT])
    qtbot.waitUntil(lambda: panel.queue[0].status == WAITING, timeout=5000)
    return panel.queue[0]


def test_essential_files_come_checked_and_the_total_shows(panel, catalog, qtbot):
    queued = _listed(panel, catalog, qtbot)
    assert queued.chosen == {"obs.hdr", "obs.img"}
    assert panel.total.text() == "2 files, 5.1 KB"
    browse = queued.item.child(2)  # what's checked comes first
    assert browse.text(0) == "obs_browse.png"
    browse.setCheckState(0, Qt.CheckState.Checked)
    assert panel.total.text() == "3 files, 5.4 KB"
    panel.add(catalog, [PRODUCT])  # already on the list
    assert len(panel.queue) == 1


def test_the_queue_downloads_into_the_product_folder_and_opens_the_data(
    panel, catalog, qtbot, tmp_path
):
    _listed(panel, catalog, qtbot)
    with qtbot.waitSignal(panel.sigOpen, timeout=10000) as opened:
        panel.downloadButton.click()
    qtbot.waitUntil(lambda: panel.downloadButton.isEnabled(), timeout=10000)
    folder = tmp_path / "downloads" / "archive" / "mars_obs" / "obs"
    assert sorted(p.name for p in folder.iterdir()) == ["obs.hdr", "obs.img"]
    assert (folder / "obs.img").read_bytes() == FILES["obs.img"]
    assert opened.args[0] == [folder / "obs.hdr"]  # one per image, the header
    assert panel.queue[0].status == DONE
    assert "1 products downloaded" in panel.status.text()


def test_without_its_essential_files_a_product_isnt_opened(panel, catalog, qtbot):
    queued = _listed(panel, catalog, qtbot)
    queued.item.child(1).setCheckState(0, Qt.CheckState.Unchecked)  # obs.img
    opened = []
    panel.sigOpen.connect(opened.append)
    panel.downloadButton.click()
    qtbot.waitUntil(lambda: queued.status == DONE, timeout=10000)
    qtbot.waitUntil(lambda: panel.downloadButton.isEnabled(), timeout=10000)
    assert opened == []


def test_the_list_exports_as_a_csv(panel, catalog, qtbot, tmp_path):
    _listed(panel, catalog, qtbot)
    panel.exportTo(tmp_path / "list.csv")
    with open(tmp_path / "list.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["file"] for r in rows] == ["obs.hdr", "obs.img"]
    assert all("archive" in r["target"] for r in rows)


def test_only_one_openable_file_per_image():
    found = openableFiles(
        [Path("a/obs.img"), Path("a/obs.hdr"), Path("a/obs.lbl"), Path("a/b.tif")]
    )
    assert sorted(found) == [Path("a/b.tif"), Path("a/obs.hdr")]


def test_the_columns_can_be_dragged_wider(panel):
    header = panel.tree.header()
    assert header.sectionResizeMode(0) == header.ResizeMode.Interactive
    header.resizeSection(0, 900)
    assert header.sectionSize(0) == 900


def test_check_all_essential_none_and_by_type(panel, catalog, qtbot):
    queued = _listed(panel, catalog, qtbot)
    panel.checkFiles(lambda f: True)
    assert queued.chosen == set(FILES)
    assert panel.total.text().startswith("3 files")
    panel.checkFiles(lambda f: False)
    assert queued.chosen == set()
    panel.checkFiles(lambda f: f.role == "browse", add=True)
    assert queued.chosen == {"obs_browse.png"}
    browse = next(
        queued.item.child(r)
        for r in range(queued.item.childCount())
        if queued.item.child(r).text(0) == "obs_browse.png"
    )
    assert browse.checkState(0) == Qt.CheckState.Checked
    panel.checkFiles(lambda f: f.essential)
    assert queued.chosen == {"obs.hdr", "obs.img"}


def test_checks_apply_to_the_selected_products_only(panel, catalog, qtbot):
    other = Product("obs2", "Another", "mars_obs", shapely.box(2, 2, 3, 3))
    panel.add(catalog, [PRODUCT, other])
    qtbot.waitUntil(lambda: all(q.status == WAITING for q in panel.queue), timeout=5000)
    first, second = panel.queue
    first.item.setSelected(True)
    panel.checkFiles(lambda f: False)
    assert first.chosen == set() and second.chosen == {"obs.hdr", "obs.img"}


def test_select_by_status_then_download_only_those(panel, catalog, qtbot):
    other = Product("obs2", "Another", "mars_obs", shapely.box(2, 2, 3, 3))
    panel.add(catalog, [PRODUCT, other])
    qtbot.waitUntil(lambda: all(q.status == WAITING for q in panel.queue), timeout=5000)
    first, second = panel.queue
    panel._setStatus(second, "Failed: the server returned 500.")
    panel.selectProducts(lambda s: s.startswith("Failed"))
    assert [i.text(0) for i in panel.tree.selectedItems()] == ["obs2"]
    panel.downloadButton.click()
    qtbot.waitUntil(lambda: panel.downloadButton.isEnabled(), timeout=10000)
    assert second.status == DONE and first.status == WAITING


def test_a_missing_file_is_marked_and_the_rest_are_downloaded(
    panel, server, qtbot, tmp_path
):
    class Broken(Catalog):
        catalogId = "broken"
        name = "Broken links"

        def files(self, product):
            return [
                RemoteFile(
                    "obs.hdr", f"{server}/obs.hdr", 100, role="data", essential=True
                ),
                RemoteFile(
                    "gone.img", f"{server}/gone.img", 9, role="data", essential=True
                ),
            ]

    panel.add(Broken(), [PRODUCT])
    queued = panel.queue[0]
    qtbot.waitUntil(lambda: queued.status == WAITING, timeout=5000)
    opened = []
    panel.sigOpen.connect(opened.append)
    panel.downloadButton.click()
    qtbot.waitUntil(lambda: panel.downloadButton.isEnabled(), timeout=10000)
    assert queued.status.startswith("Failed: 1 of 2 files")
    folder = tmp_path / "downloads" / "broken" / "mars_obs" / "obs"
    assert (folder / "obs.hdr").exists() and not (folder / "gone.img").exists()
    gone = next(
        queued.item.child(r)
        for r in range(queued.item.childCount())
        if queued.item.child(r).text(0) == "gone.img"
    )
    assert gone.text(2) == "data: not downloaded" and "404" in gone.toolTip(2)
    assert opened == []  # a header without its cube isn't opened
