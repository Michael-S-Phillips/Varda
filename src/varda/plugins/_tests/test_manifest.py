"""plugin.toml is read and checked, with messages a user can act on."""

import pytest

from varda.plugins.manifest import API_VERSION, PluginError, readManifest


def _plugin(tmp_path, toml: str, entry: str | None = "plugin.py"):
    folder = tmp_path / "p"
    folder.mkdir()
    (folder / "plugin.toml").write_text(toml)
    if entry:
        (folder / entry).write_text("")
    return folder


def test_a_complete_manifest_is_read(tmp_path):
    folder = _plugin(
        tmp_path,
        '[plugin]\nname = "band-depth"\nversion = "0.1.0"\n'
        'description = "d"\nauthor = "a"\nrequires = ["numpy"]\n',
    )
    manifest = readManifest(folder)
    assert (manifest.name, manifest.version, manifest.api) == (
        "band-depth",
        "0.1.0",
        API_VERSION,
    )
    assert manifest.requires == ("numpy",) and manifest.missingRequirements() == []


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ("", "[plugin]"),
        ('[plugin]\nversion = "1"\n', "name"),
        ('[plugin]\nname = "Bad Name"\nversion = "1"\n', "lowercase"),
        ('[plugin]\nname = "p"\nversion = "1"\napi = "9"\n', "API 9"),
        ('[plugin]\nname = "p"\nversion = "1"\nentry = "missing.py"\n', "missing.py"),
        ("[plugin\n", "can't be read"),
    ],
)
def test_problems_are_explained(tmp_path, toml, message):
    with pytest.raises(PluginError, match=message.replace("[", r"\[")):
        readManifest(_plugin(tmp_path, toml))


def test_a_missing_requirement_is_reported(tmp_path):
    folder = _plugin(
        tmp_path,
        '[plugin]\nname = "p"\nversion = "1"\nrequires = ["no_such_module_xyz"]\n',
    )
    assert readManifest(folder).missingRequirements() == ["no_such_module_xyz"]
