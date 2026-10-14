"""The example plugins in docs/plugins/examples install, contribute what
they say, and import nothing from Varda but varda.api."""

import ast
from pathlib import Path

import pytest

from varda.plugins.plugin_manager import VardaPluginManager

EXAMPLES = Path(__file__).parents[4] / "docs" / "plugins" / "examples"
FOLDERS = sorted(p for p in EXAMPLES.iterdir() if (p / "plugin.toml").is_file())


class _Sink:
    def __init__(self):
        self.active = {}

    def add(self, plugin, contributions):
        self.active[plugin] = contributions
        return lambda: self.active.pop(plugin)


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_an_example_installs_and_contributes(folder, tmp_path):
    manager = VardaPluginManager(pluginsFolder=tmp_path)
    sink = _Sink()
    manager.loadInstalled(sink)
    record = manager.install(folder)
    assert record.loaded, record.error
    assert sink.active[record.name]


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_an_example_imports_only_the_plugin_api(folder):
    for path in folder.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                if name == "varda" or name.startswith("varda."):
                    assert name == "varda.api", f"{path.name} imports {name}"
