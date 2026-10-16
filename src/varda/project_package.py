"""Packaged projects: one ``.varda.zip`` holding everything a session needs,
so that anyone with Varda can open the project on their own computer, as a
packaged Illustrator document can be. No widgets: ``writePackage`` runs
on a worker thread.

Inside: the session (``session.varda``, its paths relative to the package),
every image file with its companions (an ENVI header, a PDS label, GDAL's
``.aux.xml``, world files; their names kept, so the pointers inside them
still work), the other files workspaces refer to (a 3D Terrain line file,
say), results that exist only in memory (as ENVI), and ``manifest.json``:
the Varda version, when it was made, where each image came from, and every
file's size and SHA-256, for anyone checking they have the same data.
Opening one is opening a session (``session.openSessionBundle``).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import attrs
from attrs import frozen

from varda.common.entities import VardaRaster
from varda.common.expressions import words
from varda.image_loading.raster_writer import writeRaster
from varda.session import (
    BUNDLE_DATA_FOLDER,
    BUNDLE_SESSION_NAME,
    BUNDLE_SUFFIX,
    SESSION_SUFFIX,
    SessionState,
    captureSession,
    writeSession,
)
from varda.version import vardaVersion

MANIFEST_NAME = "manifest.json"
LARGE_BYTES = 1 << 30  # bigger packages ask before they're written
# Files beside an image that belong to it: its name, another suffix
COMPANION_SUFFIXES = {
    ".hdr",
    ".lbl",
    ".aux.xml",
    ".aux",
    ".ovr",
    ".prj",
    ".wld",
    ".tfw",
    ".tifw",
    ".jgw",
    ".pgw",
    ".rpb",
    ".imd",
    ".xml",
}
# Labels and headers point at their data, and a shapefile is several files:
# everything sharing their name goes along
TAKE_ALL_SUFFIXES = {".lbl", ".xml", ".hdr", ".shp"}

Progress = Callable[[int, str], None]


def _stem(path: Path) -> str:
    return path.name.split(".")[0].lower()


def companionFiles(path: str | Path) -> list[Path]:
    """The file and the files beside it that belong to it (none if it's gone)."""
    main = Path(path)
    if not main.is_file():
        return []
    takeAll = main.suffix.lower() in TAKE_ALL_SUFFIXES
    found = [main]
    for other in sorted(main.parent.iterdir()):
        if other == main or not other.is_file():
            continue
        if other.name.lower().startswith(main.name.lower() + "."):
            found.append(other)  # X.IMG.HDR, X.tif.aux.xml, X.tif.ovr
        elif _stem(other) == _stem(main):
            rest = other.name[len(other.name.split(".")[0]) :].lower()
            if takeAll or rest in COMPANION_SUFFIXES:
                found.append(other)
    return found


def _estimatedBytes(image: VardaRaster) -> int:
    """What an image held only in memory takes written as float32 ENVI."""
    return int(image.width * image.height * image.bandCount * 4)


@frozen
class PackagePlan:
    """What a package will hold, worked out before anything is written."""

    images: tuple[tuple[VardaRaster, tuple[Path, ...]], ...]  # file-backed
    inMemory: tuple[VardaRaster, ...]  # written into the package as ENVI
    files: tuple[tuple[str, tuple[Path, ...]], ...]  # (as referred to, files)
    missing: tuple[str, ...]  # files a workspace refers to that aren't there

    @property
    def totalBytes(self) -> int:
        copied = {f for _, group in self.images for f in group}
        copied |= {f for _, group in self.files for f in group}
        return sum(f.stat().st_size for f in copied) + sum(
            _estimatedBytes(i) for i in self.inMemory
        )

    @property
    def isLarge(self) -> bool:
        return self.totalBytes > LARGE_BYTES


def referencedPaths(value: object) -> list[str]:
    """Every ``"path"`` entry in a workspace's state (a line file's, say)."""
    if isinstance(value, dict):
        return [
            found
            for key, item in value.items()
            for found in (
                [item]
                if key == "path" and isinstance(item, str)
                else referencedPaths(item)
            )
        ]
    if isinstance(value, list):
        return [found for item in value for found in referencedPaths(item)]
    return []


def relocatedPaths(value: object, moved: dict[str, str]) -> object:
    """A workspace's state with its ``"path"`` entries replaced by ``moved``."""
    if isinstance(value, dict):
        return {
            key: (
                moved.get(item, item)
                if key == "path" and isinstance(item, str)
                else relocatedPaths(item, moved)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [relocatedPaths(item, moved) for item in value]
    return value


def planPackage(
    images: Sequence[VardaRaster], workspaces: Iterable[object]
) -> PackagePlan:
    fileBacked, inMemory = [], []
    for image in images:
        if image.filePath:
            fileBacked.append((image, tuple(companionFiles(image.filePath))))
        else:
            inMemory.append(image)
    capture = captureSession(images, workspaces, {id(i): "memory" for i in inMemory})
    files: dict[str, tuple[Path, ...]] = {}
    missing = []
    for workspace in capture.state.workspaces:
        for path in referencedPaths(workspace.extra):
            group = companionFiles(path)
            if group:
                files.setdefault(path, tuple(group))
            elif path not in missing:
                missing.append(path)
    return PackagePlan(
        tuple(fileBacked), tuple(inMemory), tuple(files.items()), tuple(missing)
    )


def packageTarget(path: str | Path) -> Path:
    """``path`` with the package suffix."""
    target = Path(path)
    if target.name.endswith(BUNDLE_SUFFIX):
        return target
    return target.with_name(target.name.removesuffix(SESSION_SUFFIX) + BUNDLE_SUFFIX)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


RESULT_PLACEHOLDER = "varda-result:"  # in a captured session, a result's path


def capturePackage(
    plan: PackagePlan, images: Sequence[VardaRaster], workspaces: Iterable[object]
) -> SessionState:
    """The session to package. It reads the workspaces' state, so call it
    where they live (the GUI thread); ``writePackage`` can then run anywhere."""
    placeholders = {
        id(image): f"{RESULT_PLACEHOLDER}{index}"
        for index, image in enumerate(plan.inMemory)
    }
    return captureSession(images, workspaces, placeholders).state


def writePackage(
    plan: PackagePlan,
    state: SessionState,
    path: str | Path,
    progress: Progress | None = None,
) -> Path:
    """Write the planned package of ``state`` (``capturePackage``) to
    ``path`` (``.varda.zip`` added if missing)."""
    report = progress or (lambda percent, message: None)
    target = packageTarget(path)
    free = shutil.disk_usage(target.parent).free
    if plan.totalBytes > free:
        raise OSError(
            f"The package needs about {formatBytes(plan.totalBytes)}, but only "
            f"{formatBytes(free)} is free there."
        )
    with tempfile.TemporaryDirectory(
        dir=target.parent, prefix=".varda-package-"
    ) as tmp:
        root = Path(tmp)
        copies: dict[str, Path] = {}  # name inside the package -> file to copy
        inside: dict[str, str] = {}  # a file's path -> its path inside
        manifestImages = []
        for index, (image, group) in enumerate(plan.images):
            folder = (
                f"{BUNDLE_DATA_FOLDER}/{index + 1:02d}_{words(image.name) or 'image'}"
            )
            names = [f"{folder}/{file.name}" for file in group]
            copies.update(zip(names, group))
            inside[str(group[0])] = names[0]
            manifestImages.append(
                {"name": image.name, "source": str(group[0]), "files": names}
            )
        for index, image in enumerate(plan.inMemory):
            report(2, f"writing {image.name}")
            folder = root / BUNDLE_DATA_FOLDER / "results"
            folder.mkdir(parents=True, exist_ok=True)
            out = writeRaster(
                image, folder / f"{index + 1:02d}_{words(image.name) or 'result'}.img"
            )
            inside[f"{RESULT_PLACEHOLDER}{index}"] = out.relative_to(root).as_posix()
            manifestImages.append(
                {
                    "name": image.name,
                    "source": "held in memory (an analysis result)",
                    "files": [
                        f.relative_to(root).as_posix()
                        for f in sorted(folder.glob(out.stem + ".*"))
                    ],
                }
            )
        moved: dict[str, str] = {}
        for index, (referred, group) in enumerate(plan.files):
            folder = f"{BUNDLE_DATA_FOLDER}/files/{index + 1:02d}"
            names = [f"{folder}/{file.name}" for file in group]
            copies.update(zip(names, group))
            moved[referred] = names[0]  # relative to the session file

        packaged = SessionState(
            tuple(str(root / inside.get(p, p)) for p in state.images),
            tuple(
                attrs.evolve(
                    w,
                    images=tuple(str(root / inside.get(p, p)) for p in w.images),
                    extra=relocatedPaths(w.extra, moved),
                )
                for w in state.workspaces
            ),
        )
        session = writeSession(packaged, root / BUNDLE_SESSION_NAME, relativeTo=root)

        checksums: dict[str, dict] = {}
        total = max(sum(f.stat().st_size for f in copies.values()), 1)
        done = 0
        with zipfile.ZipFile(
            target, "w", zipfile.ZIP_DEFLATED, compresslevel=1
        ) as archive:
            archive.write(session, BUNDLE_SESSION_NAME)
            results = [
                f for f in sorted(root.rglob("*")) if f.is_file() and f != session
            ]
            for file, name in [(f, f.relative_to(root).as_posix()) for f in results] + [
                (f, n) for n, f in copies.items()
            ]:
                report(5 + int(90 * done / total), f"adding {file.name}")
                archive.write(file, name)
                checksums[name] = {
                    "bytes": file.stat().st_size,
                    "sha256": _sha256(file),
                }
                if name in copies:
                    done += file.stat().st_size
            manifest = {
                "format": "varda-package",
                "version": 1,
                "varda": vardaVersion(),
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "images": manifestImages,
                "files": checksums,
                "missing": list(plan.missing),
            }
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
    report(100, "done")
    return target


def formatBytes(count: int) -> str:
    size = float(count)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def verifyPackage(folder: str | Path) -> list[str]:
    """Files of an opened package missing or differing from its manifest."""
    root = Path(folder)
    manifest = json.loads((root / MANIFEST_NAME).read_text())
    return [
        name
        for name, entry in manifest["files"].items()
        if not (root / name).is_file() or _sha256(root / name) != entry["sha256"]
    ]
