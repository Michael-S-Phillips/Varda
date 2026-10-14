"""``plugin.toml``: what a plugin says about itself.

A plugin is a folder holding ``plugin.toml``, its entry module and anything
else it needs::

    [plugin]
    name = "band-depth-1900"          # unique; lowercase letters, digits, - and _
    version = "0.1.0"
    description = "Band depth at 1.9 µm, against the 1.8-2.1 µm continuum"
    author = "Michael Phillips"
    api = "1"                         # the varda.api version it was written for
    entry = "plugin.py"               # the module that implements the hooks
    requires = ["scipy"]              # optional: importable modules it needs
"""

from __future__ import annotations

import re
import tomllib
from importlib.util import find_spec
from pathlib import Path

import attrs

MANIFEST_NAME = "plugin.toml"
API_VERSION = "1"  # bump only for breaking changes to varda.api
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class PluginError(Exception):
    """A plugin that can't be installed or loaded, with a message for the user."""


@attrs.frozen
class PluginManifest:
    name: str
    version: str
    description: str = ""
    author: str = ""
    api: str = API_VERSION
    entry: str = "plugin.py"
    requires: tuple[str, ...] = ()

    def missingRequirements(self) -> list[str]:
        """Required modules that can't be imported in this Varda."""
        return [name for name in self.requires if find_spec(name) is None]


def readManifest(folder: Path) -> PluginManifest:
    """The folder's manifest, checked; raises PluginError saying what's wrong."""
    path = Path(folder) / MANIFEST_NAME
    if not path.is_file():
        raise PluginError(f"{Path(folder).name} has no {MANIFEST_NAME}.")
    try:
        document = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise PluginError(f"{MANIFEST_NAME} can't be read: {error}") from error
    table = document.get("plugin")
    if not isinstance(table, dict):
        raise PluginError(f"{MANIFEST_NAME} needs a [plugin] table.")
    for key in ("name", "version"):
        if not isinstance(table.get(key), str) or not table[key].strip():
            raise PluginError(f"{MANIFEST_NAME} needs a {key}.")
    name = table["name"].strip()
    if not _NAME.match(name):
        raise PluginError(
            f"Plugin name {name!r} may use only lowercase letters, digits, - and _."
        )
    api = str(table.get("api", API_VERSION))
    if api != API_VERSION:
        raise PluginError(
            f"{name} was written for Varda plugin API {api}; this Varda supports "
            f"API {API_VERSION}."
        )
    entry = str(table.get("entry", "plugin.py"))
    if not (Path(folder) / entry).is_file():
        raise PluginError(f"{name}'s entry module {entry} is missing.")
    requires = table.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
        raise PluginError(f"{MANIFEST_NAME}'s requires must be a list of names.")
    return PluginManifest(
        name=name,
        version=table["version"].strip(),
        description=str(table.get("description", "")),
        author=str(table.get("author", "")),
        api=api,
        entry=entry,
        requires=tuple(requires),
    )
