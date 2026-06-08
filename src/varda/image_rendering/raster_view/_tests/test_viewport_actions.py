"""Tests for the viewport context-menu action module."""

from varda.image_rendering.raster_view import viewport_actions as va


def test_holder_roundtrip():
    va.setCurrentClickContext(None)
    assert va.getCurrentClickContext() is None
    ctx = va.ViewportClickContext(placeTemplate=lambda: None, lockColumn=False, hasTemplate=True)
    va.setCurrentClickContext(ctx)
    assert va.getCurrentClickContext() is ctx
    va.setCurrentClickContext(None)


def test_actions_registered_for_viewport_menu():
    ids = {a.id for a in va.VIEWPORT_ACTIONS}
    assert "varda.viewport.place_template" in ids
    # all actions target the viewport context menu
    for a in va.VIEWPORT_ACTIONS:
        assert any(rule.id == va.VIEWPORT_CONTEXT_MENU_ID for rule in a.menus)
