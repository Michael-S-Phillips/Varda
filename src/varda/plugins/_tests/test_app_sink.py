"""Plugin analyses appear in the Processing menu, and leave it again."""

import pytest
from app_model import Application

from varda._actions._menu_ids import MenuId
from varda._actions._processing_actions import categoryMenuId
from varda.api import Analysis
from varda.image_loading.data_sources.registry import datasource_registry
from varda.plugins.app_sink import AppContributionSink
from varda.plugins.plugin_manager import Contributions


class _NewCategory(Analysis):
    analysisId = "sink_test"
    name = "Sink Test"
    category = "My Plugin Tools"


class _BuiltinCategory(Analysis):
    analysisId = "sink_test_builtin"
    name = "Sink Test Builtin"
    category = "Spectral Parameters"


class _FakeSource:
    pass


@pytest.fixture
def app():
    app = Application("varda-test-sink")
    yield app
    Application.destroy("varda-test-sink")


def _menuItems(app, menuId):
    try:
        return list(app.menus.get_menu(menuId))
    except KeyError:  # a menu with nothing left in it
        return []


def test_analyses_become_menu_items_and_go_away(app):
    sink = AppContributionSink(app)
    remove = sink.add(
        "my-plugin", Contributions(analyses=(_NewCategory, _BuiltinCategory))
    )
    assert "varda.plugin.my_plugin.sink_test" in app.commands
    submenu = categoryMenuId(MenuId.PROCESSING, "My Plugin Tools")
    assert any(
        getattr(i, "submenu", None) == submenu
        for i in _menuItems(app, MenuId.PROCESSING)
    )
    remove()
    assert "varda.plugin.my_plugin.sink_test" not in app.commands
    assert not any(
        getattr(i, "submenu", None) == submenu
        for i in _menuItems(app, MenuId.PROCESSING)
    )


def test_a_shared_category_stays_until_its_last_plugin_goes(app):
    sink = AppContributionSink(app)
    first = sink.add("a", Contributions(analyses=(_NewCategory,)))
    second = sink.add("b", Contributions(analyses=(_NewCategory,)))
    submenu = categoryMenuId(MenuId.PROCESSING, "My Plugin Tools")
    count = lambda: sum(
        getattr(i, "submenu", None) == submenu
        for i in _menuItems(app, MenuId.PROCESSING)
    )  # noqa: E731
    assert count() == 1
    first()
    assert count() == 1
    second()
    assert count() == 0


def test_file_formats_join_the_registry_and_leave_it(app):
    sink = AppContributionSink(app)
    before = len(datasource_registry)
    remove = sink.add(
        "fmt", Contributions(dataSources=(("Test Format", (".tst",), _FakeSource),))
    )
    assert datasource_registry[-1].formatName == "Test Format"
    remove()
    assert len(datasource_registry) == before
