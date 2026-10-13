"""User plugins in the plugins folder load when running from source."""

import sys
import textwrap

from varda.plugins.plugin_manager import VardaPluginManager

PLUGIN = textwrap.dedent(
    """
    from varda.plugins import hookimpl

    loaded = []

    @hookimpl
    def onLoad(app):
        loaded.append(app)
    """
)


def _manager(folder, monkeypatch, frozen=None):
    if frozen is not None:
        monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    manager = VardaPluginManager()
    manager._registerPluginsInFolder(folder)
    return manager


def test_a_plugin_file_is_loaded_and_called(tmp_path, monkeypatch):
    (tmp_path / "my_plugin.py").write_text(PLUGIN)
    manager = _manager(tmp_path, monkeypatch)
    manager.hook.onLoad(app="the app")
    (plugin,) = [
        p for p in manager.pm.get_plugins() if getattr(p, "loaded", None) is not None
    ]
    assert plugin.loaded == ["the app"]


def test_a_plugin_package_is_loaded(tmp_path, monkeypatch):
    package = tmp_path / "my_package"
    package.mkdir()
    (package / "__init__.py").write_text(PLUGIN)
    manager = _manager(tmp_path, monkeypatch)
    names = [manager.pm.get_name(p) for p in manager.pm.get_plugins()]
    assert any("my_package" in str(n) for n in names)


def test_examples_and_private_files_are_skipped(tmp_path, monkeypatch):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "__init__.py").write_text(PLUGIN)
    (tmp_path / "_helper.py").write_text(PLUGIN)
    before = len(VardaPluginManager().pm.get_plugins())
    manager = _manager(tmp_path, monkeypatch)
    assert len(manager.pm.get_plugins()) == before


def test_a_broken_plugin_is_logged_not_fatal(tmp_path, monkeypatch, caplog):
    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')")
    (tmp_path / "good.py").write_text(PLUGIN)
    manager = _manager(tmp_path, monkeypatch)
    assert "broken" in caplog.text
    assert any(getattr(p, "loaded", None) is not None for p in manager.pm.get_plugins())


def test_the_packaged_app_skips_the_folder(tmp_path, monkeypatch):
    (tmp_path / "my_plugin.py").write_text(PLUGIN)
    manager = _manager(tmp_path, monkeypatch, frozen=True)
    assert not any(
        getattr(p, "loaded", None) is not None for p in manager.pm.get_plugins()
    )
