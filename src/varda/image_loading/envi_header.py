"""Saving metadata edited in Varda (Image Properties) into an ENVI header.
Only the edited fields change; every other field stays as written, and the
header is backed up (``.bak``) before its first edit. GDAL keeps a copy of
the header's fields in the data file's ``.aux.xml``, which it reads in
preference to the header, so that copy is dropped (the file backed up too)
for GDAL to read the header again. No Qt."""

from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ElementTree
from pathlib import Path

# Varda's metadata keys and the header fields they're written to
HEADER_FIELDS = {
    "nodata": "data ignore value",
    "wavelengthUnits": "wavelength units",
    "wavelengths": "wavelength",
    "bandNames": "band names",
    "fwhm": "fwhm",
    "bbl": "bbl",
    "description": "description",
}
_FIELD = re.compile(r"^\s*([^=]+?)\s*=\s*(.*)$")


def headerFor(dataPath: str | Path) -> Path | None:
    """An ENVI data file's header: ``X.hdr`` or ``X.img.hdr``, any case."""
    data = Path(dataPath)
    wanted = {f"{data.stem}.hdr".lower(), f"{data.name}.hdr".lower()}
    if not data.parent.is_dir():
        return None
    return next(
        (f for f in sorted(data.parent.iterdir()) if f.name.lower() in wanted), None
    )


def readHeader(path: str | Path) -> list[tuple[str, str]]:
    """The header's fields in order, as (name, value as written); a value in
    braces may span lines."""
    fields: list[tuple[str, str]] = []
    pending: tuple[str, list[str]] | None = None  # a value still in braces
    for line in Path(path).read_text().splitlines()[1:]:  # after "ENVI"
        if pending is not None:
            pending[1].append(line)
            if "}" in line:
                fields.append((pending[0], "\n".join(pending[1])))
                pending = None
            continue
        match = _FIELD.match(line)
        if match is None:
            continue
        name, value = match.group(1).strip().lower(), match.group(2).strip()
        if value.startswith("{") and "}" not in value:
            pending = (name, [value])
        else:
            fields.append((name, value))
    return fields


def _written(key: str, value) -> str:
    if key in ("wavelengths", "fwhm"):
        return "{ " + ", ".join(f"{float(v):g}" for v in value) + " }"
    if key == "bbl":
        return "{ " + ", ".join(str(int(v)) for v in value) + " }"
    if key == "bandNames":
        return "{ " + ", ".join(str(v).replace(",", " ") for v in value) + " }"
    if key == "description":
        return "{ " + str(value).replace("}", ")") + " }"
    if key == "nodata":
        return f"{float(value):g}"
    return str(value)


def _backedUp(path: Path) -> None:
    backup = path.with_name(path.name + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def saveToHeader(dataPath: str | Path, overrides: dict) -> Path:
    """Write edited metadata (``VardaRaster.metadataOverrides`` keys) into
    the header of the ENVI data file at ``dataPath``; returns the header. A
    no-data value of None removes the field."""
    header = headerFor(dataPath)
    if header is None:
        raise FileNotFoundError(f"{Path(dataPath).name} has no ENVI header beside it.")
    _backedUp(header)
    fields = dict(readHeader(header))
    order = [name for name, _ in readHeader(header)]
    for key, value in overrides.items():
        name = HEADER_FIELDS[key]
        if value is None:
            fields.pop(name, None)
            continue
        if name not in fields:
            order.append(name)
        fields[name] = _written(key, value)
    lines = ["ENVI"] + [f"{name} = {fields[name]}" for name in order if name in fields]
    header.write_text("\n".join(lines) + "\n")
    _dropGdalCopy(Path(dataPath))
    return header


def _dropGdalCopy(dataPath: Path) -> None:
    """Remove GDAL's copy of the header (its ENVI metadata and band
    descriptions) from the data file's ``.aux.xml``, keeping the rest
    (statistics, say)."""
    aux = dataPath.with_name(dataPath.name + ".aux.xml")
    if not aux.is_file():
        return
    _backedUp(aux)
    tree = ElementTree.parse(aux)
    root = tree.getroot()
    for metadata in root.findall("Metadata"):
        if metadata.get("domain") == "ENVI":
            root.remove(metadata)
    for band in root.findall("PAMRasterBand"):
        for description in band.findall("Description"):
            band.remove(description)
    tree.write(aux)
