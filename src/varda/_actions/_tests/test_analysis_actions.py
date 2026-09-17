"""An Analysis menu offers running an analysis; thumbnails offer Analyze…."""

from varda._actions import ALL_ACTIONS
from varda._actions._menu_ids import MENUBAR, MenuId
from varda.all_images_view_list import image_list_actions as ila


def test_analysis_menu_exists_with_a_run_action():
    assert (MenuId.ANALYSIS, "Analysis") in MENUBAR
    (action,) = [a for a in ALL_ACTIONS if a.id == "varda.analysis.run"]
    assert action.title == "Run Analysis…"
    assert any(rule.id == MenuId.ANALYSIS for rule in action.menus)
    assert action.enablement is not None  # needs an image


def test_image_list_menu_offers_analyze():
    (action,) = [a for a in ila.IMAGE_LIST_ACTIONS if a.id == ila.ANALYZE_ID]
    assert action.title == "Analyze…"
    assert any(rule.id == ila.IMAGE_LIST_CONTEXT_MENU_ID for rule in action.menus)
