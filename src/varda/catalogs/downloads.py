"""Downloading a product's files, for any catalog.

A file goes to ``<name>.part`` first: an interrupted download resumes from
there with an HTTP range request, and the file only takes its name once it
is complete and its checksum (when the catalog gives one) matches. A file
already there, complete, isn't downloaded again. Each product has its own
folder: ``<root>/<catalog>/<collection>/<product>/``. Beside each file
downloaded for a product, ``<file>.varda-source.json`` records where it came
from (``writeSourceRecord``); Varda reads it when it opens the file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shlex
import ssl
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

import certifi

from varda.catalogs.catalog import CatalogError, Product, RemoteFile
from varda.common.provenance import SOURCE_SUFFIX
from varda.version import vardaVersion

CHUNK = 1 << 20
TIMEOUT_S = 60


def _safe(name: str) -> str:
    """A folder name from a catalog's text."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "unnamed"


def productFolder(root: Path, catalogId: str, product: Product) -> Path:
    return root / _safe(catalogId) / _safe(product.collection) / _safe(product.id)


def _hasher(checksum: str):
    if not checksum:
        return None, ""
    kind, _, value = checksum.partition(":")
    if kind not in ("md5", "sha256") or not value:
        return None, ""
    return hashlib.new(kind), value.lower()


def _digest(path: Path, checksum: str) -> bool:
    """Whether the file matches the checksum (True when there's none)."""
    hasher, expected = _hasher(checksum)
    if hasher is None:
        return True
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            hasher.update(chunk)
    return hasher.hexdigest() == expected


def _exactSize(file: RemoteFile) -> int | None:
    return file.size if file.exactSize else None


def _complete(path: Path, file: RemoteFile) -> bool:
    size = _exactSize(file)
    return (
        path.exists()
        and (size is None or path.stat().st_size == size)
        and _digest(path, file.checksum)
    )


def download(
    file: RemoteFile,
    target: Path,
    progress: Callable[[int, int | None], None] = lambda done, total: None,
    cancelled: threading.Event | None = None,
    headers: Mapping[str, str] | None = None,
) -> Path:
    """Download ``file`` to ``target``, resuming a partial download.
    ``progress(bytesDone, bytesTotal)``. Raises CatalogError (also when
    canceled, keeping what was downloaded for next time)."""
    if _complete(target, file):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    start = part.stat().st_size if part.exists() else 0
    exact = _exactSize(file)
    if exact is not None and start > exact:
        part.unlink()
        start = 0
    request = urllib.request.Request(file.url, headers=dict(headers or {}))
    if start:
        request.add_header("Range", f"bytes={start}-")
    context = ssl.create_default_context(cafile=certifi.where())
    expected: int | None = None  # bytes the server says the file has
    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT_S,
            context=context if file.url.startswith("https") else None,
        ) as response:
            resumed = start and response.status == 206
            mode = "ab" if resumed else "wb"
            done = start if resumed else 0
            length = response.headers.get("Content-Length")
            expected = done + int(length) if length else None
            total = exact or expected or file.size
            with open(part, mode) as out:
                while chunk := response.read(CHUNK):
                    if cancelled is not None and cancelled.is_set():
                        raise CatalogError("The download was canceled.")
                    out.write(chunk)
                    done += len(chunk)
                    progress(done, total)
    except CatalogError:
        raise
    except urllib.error.HTTPError as error:
        if error.code == 401 or error.code == 403:
            raise CatalogError(
                f"{file.name}: access denied (check the login)."
            ) from error
        if error.code in (404, 410):
            raise CatalogError(
                f"{file.name}: the archive doesn't have this file ({error.code}); "
                "the catalog's link to it is broken."
            ) from error
        raise CatalogError(f"{file.name}: the server returned {error.code}.") from error
    except (OSError, ValueError) as error:  # connection lost, timeouts, …
        raise CatalogError(
            f"{file.name}: the download was interrupted ({error})."
        ) from error
    complete = exact if exact is not None else expected
    if complete is not None and part.stat().st_size < complete:
        raise CatalogError(
            f"{file.name}: the download was interrupted; it will resume."
        )
    if not _digest(part, file.checksum):
        part.unlink()
        raise CatalogError(
            f"{file.name} doesn't match its published checksum; it was deleted. "
            "Try again."
        )
    part.replace(target)
    return target


def writeSourceRecord(
    path: Path, file: RemoteFile, catalog: str, product: Product
) -> Path:
    """Record beside a downloaded file where it came from and how it was
    verified (a record already there for this download is kept)."""
    sidecar = Path(str(path) + SOURCE_SUFFIX)
    if sidecar.exists() and sidecar.stat().st_mtime >= path.stat().st_mtime:
        return sidecar
    verifiedBy = "nothing"
    if _hasher(file.checksum)[0] is not None:
        verifiedBy = "checksum"
    elif _exactSize(file) is not None:
        verifiedBy = "size"
    record = {
        "catalog": catalog,
        "collection": product.collection,
        "product": product.id,
        "title": product.title,
        "file": file.name,
        "url": file.url,
        "size": path.stat().st_size,
        "checksum": file.checksum,
        "verifiedBy": verifiedBy,
        "downloaded": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vardaVersion": vardaVersion(),
    }
    sidecar.write_text(json.dumps(record, indent=2))
    return sidecar


class IncompleteDownload(CatalogError):
    """Some of a product's files couldn't be downloaded; the others were.
    ``paths`` are the downloaded files (in order), ``failures`` the reasons."""

    def __init__(self, paths: list[Path], failures: list[str], total: int):
        missing = len(failures)
        super().__init__(
            f"{missing} of {total} files couldn't be downloaded: " + " ".join(failures)
        )
        self.paths = paths
        self.failures = failures


def downloadProduct(
    files: Iterable[RemoteFile],
    folder: Path,
    progress: Callable[[float, str], None] = lambda fraction, message: None,
    cancelled: threading.Event | None = None,
    headers: Mapping[str, str] | None = None,
    *,
    catalog: str = "",
    product: Product | None = None,
) -> list[Path]:
    """Download a product's files into its folder, in order; progress is the
    share of bytes done (by file count when sizes are unknown). A file that
    fails doesn't stop the others: they're downloaded, then
    IncompleteDownload says which failed (a cancel stops at once). With
    ``product``, each file gets a record of where it came from."""
    files = list(files)
    sizes = [f.size for f in files]
    known = all(s is not None for s in sizes)
    total = sum(s for s in sizes if s is not None) if known else len(files)
    paths: list[Path] = []
    failures: list[str] = []
    before = 0.0
    for file in files:

        def report(done: int, size: int | None, before=before, file=file) -> None:
            share = (
                (before + done) / total
                if known
                else (before + (done / size if size else 0)) / total
            )
            progress(min(share, 1.0), f"downloading {file.name}")

        try:
            path = download(file, folder / file.name, report, cancelled, headers)
            if product is not None:
                writeSourceRecord(path, file, catalog, product)
            paths.append(path)
        except CatalogError as error:
            if cancelled is not None and cancelled.is_set():
                raise
            failures.append(str(error))
        before += (file.size or 0) if known else 1
    progress(1.0, "done")
    if failures:
        raise IncompleteDownload(paths, failures, len(files))
    return paths


def exportList(
    entries: Iterable[tuple[str, Product, list[RemoteFile]]],
    path: Path,
    root: Path,
) -> None:
    """Write a download list: a CSV (product, file, URL, size, checksum,
    target) or, for a ``.sh`` path, a shell script of resumable curl
    commands."""
    rows = [
        (product, file, productFolder(root, catalogId, product) / file.name)
        for catalogId, product, files in entries
        for file in files
    ]
    if path.suffix == ".sh":
        lines = ["#!/bin/sh", "# Varda download list: resumable (curl -C -)", "set -e"]
        for _, file, target in rows:
            lines.append(f"mkdir -p {shlex.quote(str(target.parent))}")
            lines.append(
                f"curl -L -C - -o {shlex.quote(str(target))} {shlex.quote(file.url)}"
            )
        path.write_text("\n".join(lines) + "\n")
        path.chmod(0o755)
        return
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["product", "file", "url", "size", "checksum", "target"])
        for product, file, target in rows:
            writer.writerow(
                [
                    product.id,
                    file.name,
                    file.url,
                    file.size or "",
                    file.checksum,
                    target,
                ]
            )
