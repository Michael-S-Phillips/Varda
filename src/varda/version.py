"""Varda's version, from the installed package's metadata (one place to read it)."""

from importlib import metadata

DISTRIBUTION_NAMES = ("varda-app", "varda")  # the PyPI name, then the current one


def vardaVersion() -> str:
    for name in DISTRIBUTION_NAMES:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return "unknown"
