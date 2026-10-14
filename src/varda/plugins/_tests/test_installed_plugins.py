"""Installed plugins: install from a folder or zip, enable/disable, reload,
remove, and a broken plugin never stops Varda."""

import textwrap
import zipfile

import pytest

from varda.plugins.manifest import PluginError
from varda.plugins.plugin_manager import Contributions, VardaPluginManager

PLUGIN = textwrap.dedent(
    """
    from varda.api import Analysis, hookimpl

    class Doubler(Analysis):
        analysisId = "doubler"
        name = "Doubler"
        category = "Plugin Tests"
        VERSION_MARK = "v1"

        def run(self, image, reportProgress):
            return image

    @hookimpl
    def registerAnalyses():
        return [Doubler]
    """
)


class FakeSink:
    def __init__(self):
        self.active: dict[str, Contributions] = {}

    def add(self, plugin, contributions):
        self.active[plugin] = contributions
        return lambda: self.active.pop(plugin)


def _source(tmp_path, name="doubler", code=PLUGIN, toml_extra=""):
    folder = tmp_path / "src" / name
    folder.mkdir(parents=True)
    (folder / "plugin.toml").write_text(
        f'[plugin]\nname = "{name}"\nversion = "0.1.0"\n{toml_extra}'
    )
    (folder / "plugin.py").write_text(code)
    return folder


def _manager(tmp_path):
    manager = VardaPluginManager(pluginsFolder=tmp_path / "plugins")
    sink = FakeSink()
    manager.loadInstalled(sink)
    return manager, sink


def test_installing_a_folder_loads_its_analyses(tmp_path):
    manager, sink = _manager(tmp_path)
    record = manager.install(_source(tmp_path))
    assert record.loaded and record.error == ""
    (analysis,) = sink.active["doubler"].analyses
    assert analysis.name == "Doubler" and analysis.plugin == "doubler 0.1.0"
    assert (tmp_path / "plugins" / "doubler" / "plugin.toml").is_file()


def test_a_zip_with_the_plugin_in_a_folder_installs(tmp_path):
    manager, sink = _manager(tmp_path)
    folder = _source(tmp_path)
    archive = tmp_path / "doubler.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in folder.iterdir():
            zf.write(path, f"doubler/{path.name}")
    manager.install(archive)
    assert "doubler" in sink.active


def test_an_unsafe_zip_is_refused(tmp_path):
    manager, _ = _manager(tmp_path)
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../outside.txt", "x")
    with pytest.raises(PluginError, match="unsafe"):
        manager.install(archive)


def test_a_broken_plugin_is_recorded_not_raised(tmp_path):
    manager, sink = _manager(tmp_path)
    record = manager.install(_source(tmp_path, code="raise RuntimeError('oops')\n"))
    assert not record.loaded and "oops" in record.error
    assert sink.active == {}


def test_a_missing_requirement_disables_the_plugin_with_a_reason(tmp_path):
    manager, _ = _manager(tmp_path)
    record = manager.install(
        _source(tmp_path, toml_extra='requires = ["no_such_module_xyz"]\n')
    )
    assert not record.loaded and "no_such_module_xyz" in record.error


def test_disabling_persists_and_removes_contributions(tmp_path):
    manager, sink = _manager(tmp_path)
    manager.install(_source(tmp_path))
    manager.setEnabled("doubler", False)
    assert "doubler" not in sink.active
    again, againSink = _manager(tmp_path)  # Varda restarted
    assert not again.record("doubler").enabled and againSink.active == {}
    again.setEnabled("doubler", True)
    assert "doubler" in againSink.active


def test_reload_picks_up_changed_code(tmp_path):
    manager, sink = _manager(tmp_path)
    manager.install(_source(tmp_path))
    installed = tmp_path / "plugins" / "doubler" / "plugin.py"
    installed.write_text(PLUGIN.replace('VERSION_MARK = "v1"', 'VERSION_MARK = "v2"'))
    manager.reload("doubler")
    (analysis,) = sink.active["doubler"].analyses
    assert analysis.VERSION_MARK == "v2"


def test_remove_deletes_the_folder(tmp_path):
    manager, sink = _manager(tmp_path)
    manager.install(_source(tmp_path))
    manager.remove("doubler")
    assert not (tmp_path / "plugins" / "doubler").exists() and sink.active == {}


def test_a_second_install_of_the_same_name_needs_replace(tmp_path):
    manager, _ = _manager(tmp_path)
    manager.install(_source(tmp_path))
    with pytest.raises(PluginError, match="already installed"):
        manager.install(_source(tmp_path / "again"))
    manager.install(_source(tmp_path / "again2"), replace=True)
    assert manager.record("doubler").loaded
