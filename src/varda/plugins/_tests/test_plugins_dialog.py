"""Manage Plugins shows each plugin's status and what it adds, and its
buttons enable, disable and remove installed plugins."""

import textwrap

from PyQt6.QtWidgets import QMessageBox, QPushButton

from varda.plugins.plugin_manager import VardaPluginManager
from varda.plugins.plugins_dialog import ManagePluginsDialog

PLUGIN = textwrap.dedent(
    """
    from varda.api import Analysis, hookimpl

    class Tripler(Analysis):
        analysisId = "tripler"
        name = "Tripler"

    @hookimpl
    def registerAnalyses():
        return [Tripler]
    """
)


def _installed(tmp_path, name="tripler", code=PLUGIN):
    source = tmp_path / "src" / name
    source.mkdir(parents=True)
    (source / "plugin.toml").write_text(f'[plugin]\nname = "{name}"\nversion = "1.2"\n')
    (source / "plugin.py").write_text(code)
    manager = VardaPluginManager(pluginsFolder=tmp_path / "plugins")
    manager.loadInstalled()
    manager.install(source)
    return manager


def _text(dialog, row, column) -> str:
    item = dialog.table.item(row, column)
    assert item is not None
    return item.text()


def _row(dialog, name):
    for row in range(dialog.table.rowCount()):
        if _text(dialog, row, 0) == name:
            return row
    raise AssertionError(name)


def test_the_table_shows_status_and_contributions(qtbot, tmp_path):
    dialog = ManagePluginsDialog(_installed(tmp_path))
    qtbot.addWidget(dialog)
    row = _row(dialog, "tripler")
    texts = [_text(dialog, row, c) for c in range(dialog.table.columnCount())]
    assert texts[:4] == ["tripler", "1.2", "Enabled", "Tripler"]


def test_a_broken_plugin_shows_why(qtbot, tmp_path):
    dialog = ManagePluginsDialog(
        _installed(tmp_path, code="import no_such_thing_xyz\n")
    )
    qtbot.addWidget(dialog)
    status = _text(dialog, _row(dialog, "tripler"), 2)
    assert status.startswith("Not loaded") and "no_such_thing_xyz" in status


def test_buttons_disable_and_remove(qtbot, tmp_path, monkeypatch):
    manager = _installed(tmp_path)
    dialog = ManagePluginsDialog(manager)
    qtbot.addWidget(dialog)
    dialog.table.selectRow(_row(dialog, "tripler"))
    dialog.toggleButton.click()
    assert not manager.record("tripler").enabled
    assert _text(dialog, _row(dialog, "tripler"), 2) == "Disabled"
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    dialog.removeButton.click()
    assert all(r.name != "tripler" for r in manager.records)


def test_close_button_closes_the_window(qtbot, tmp_path):
    dialog = ManagePluginsDialog(VardaPluginManager(pluginsFolder=tmp_path / "plugins"))
    qtbot.addWidget(dialog)
    dialog.show()
    close = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Close")
    close.click()
    assert not dialog.isVisible()
