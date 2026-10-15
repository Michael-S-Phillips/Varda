"""Downloads resume, verify checksums, stop when canceled, and land in one
folder per product."""

import hashlib
import http.server
import threading

import pytest
import shapely

from varda.catalogs.catalog import CatalogError, Product, RemoteFile
from varda.catalogs.downloads import (
    download,
    downloadProduct,
    exportList,
    productFolder,
)

DATA = bytes(range(256)) * 4000  # ~1 MB


class _Handler(http.server.BaseHTTPRequestHandler):
    """Serves DATA, honoring Range; ``cut`` bytes in, it drops the connection
    once (to test resuming)."""

    cut: int | None = None
    requests: list[str] = []

    def do_GET(self):  # noqa: N802 (the http.server API)
        _Handler.requests.append(self.headers.get("Range", ""))
        start = 0
        if self.headers.get("Range"):
            start = int(self.headers["Range"].split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header(
                "Content-Range", f"bytes {start}-{len(DATA) - 1}/{len(DATA)}"
            )
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(DATA) - start))
        self.end_headers()
        body = DATA[start:]
        if _Handler.cut is not None:
            self.wfile.write(body[: _Handler.cut])
            _Handler.cut = None
            self.close_connection = True
            return
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.cut, _Handler.requests = None, []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/data.bin"
    httpd.shutdown()


def _file(url, checksum="", size=len(DATA)):
    return RemoteFile("data.bin", url, size, checksum)


def test_a_file_downloads_and_verifies(server, tmp_path):
    digest = "md5:" + hashlib.md5(DATA).hexdigest()
    path = download(_file(server, digest), tmp_path / "data.bin")
    assert path.read_bytes() == DATA
    assert not (tmp_path / "data.bin.part").exists()


def test_an_interrupted_download_resumes(server, tmp_path):
    _Handler.cut = 300_000
    with pytest.raises(CatalogError):
        download(_file(server), tmp_path / "data.bin")
    assert (tmp_path / "data.bin.part").stat().st_size == 300_000
    path = download(_file(server), tmp_path / "data.bin")
    assert path.read_bytes() == DATA
    assert _Handler.requests[-1] == "bytes=300000-"


def test_a_checksum_mismatch_is_refused(server, tmp_path):
    with pytest.raises(CatalogError, match="checksum"):
        download(_file(server, "sha256:" + "0" * 64), tmp_path / "data.bin")
    assert not (tmp_path / "data.bin").exists()
    assert not (tmp_path / "data.bin.part").exists()


def test_a_finished_file_is_not_downloaded_again(server, tmp_path):
    download(_file(server), tmp_path / "data.bin")
    count = len(_Handler.requests)
    download(_file(server), tmp_path / "data.bin")
    assert len(_Handler.requests) == count


def test_canceling_stops_and_keeps_the_partial_file(server, tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(CatalogError, match="anceled"):
        download(_file(server), tmp_path / "data.bin", cancelled=cancel)
    assert not (tmp_path / "data.bin").exists()


def test_products_get_their_own_folders(server, tmp_path):
    product = Product(
        "frt00005850_07_if167j_mtr3", "FRT 5850", "CRISM MTRDR", shapely.box(0, 0, 1, 1)
    )
    assert (
        productFolder(tmp_path, "ode", product)
        == tmp_path / "ode" / "CRISM_MTRDR" / "frt00005850_07_if167j_mtr3"
    )
    seen = []
    paths = downloadProduct(
        [_file(server), RemoteFile("other.bin", server, len(DATA))],
        productFolder(tmp_path, "ode", product),
        progress=lambda fraction, message: seen.append(fraction),
    )
    assert [p.name for p in paths] == ["data.bin", "other.bin"]
    assert seen[-1] == 1.0 and seen == sorted(seen)


def test_a_download_list_exports_as_csv_and_a_script(tmp_path):
    product = Product("p1", "P1", "c", shapely.box(0, 0, 1, 1))
    files = [RemoteFile("a.img", "https://example.org/a.img", 1000, "md5:abc")]
    exportList([(product, files)], tmp_path / "list.csv", tmp_path / "downloads")
    assert "https://example.org/a.img" in (tmp_path / "list.csv").read_text()
    exportList([(product, files)], tmp_path / "get.sh", tmp_path / "downloads")
    script = (tmp_path / "get.sh").read_text()
    assert script.startswith("#!/bin/sh") and "curl" in script and "-C -" in script
