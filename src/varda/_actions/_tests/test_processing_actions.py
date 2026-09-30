"""The Processing menu names each operation, grouped by category."""

from app_model.types import SubmenuItem

from varda._actions import ALL_ACTIONS
from varda._actions._menu_ids import MENUBAR, MenuId
from varda._actions._processing_actions import (
    PROCESSING_SUBMENUS,
    categoryMenuId,
    processingActions,
    processingSubmenus,
)
from varda.analysis.analysis import Analysis


class Pca(Analysis):
    analysisId = "pca"
    name = "PCA"
    category = "Transforms"

    def run(self, image, reportProgress):
        return image


class Mnf(Analysis):
    analysisId = "mnf"
    name = "MNF"
    category = "Transforms"

    def run(self, image, reportProgress):
        return image


class NeedsThing(Analysis):
    analysisId = "needs_thing"
    name = "Needs Thing"
    category = "Statistics"
    requirement = "Thing"

    @classmethod
    def isAvailable(cls):
        return False

    def run(self, image, reportProgress):
        return image


def _noCallback(analysisClass):
    return lambda: None


def test_processing_replaces_the_generic_analysis_menu():
    assert (MenuId.PROCESSING, "Processing") in MENUBAR
    assert not any(a.id == "varda.analysis.run" for a in ALL_ACTIONS)


def test_one_submenu_per_category_in_first_appearance_order():
    submenus = processingSubmenus("root", [Pca, Mnf, NeedsThing])
    assert [(parent, item.title, item.submenu) for parent, item in submenus] == [
        ("root", "Transforms", "root/transforms"),
        ("root", "Statistics", "root/statistics"),
    ]
    assert all(isinstance(item, SubmenuItem) for _p, item in submenus)


def test_one_action_per_analysis_under_its_category():
    actions = processingActions("root", "prefix", [Pca, Mnf], _noCallback)
    assert [a.id for a in actions] == ["prefix.pca", "prefix.mnf"]
    assert [a.title for a in actions] == ["PCA…", "MNF…"]
    assert all(a.menus[0].id == categoryMenuId("root", "Transforms") for a in actions)
    assert all(a.enablement.eval({"image_count": 1}) for a in actions)
    assert not any(a.enablement.eval({"image_count": 0}) for a in actions)


def test_unavailable_analysis_is_shown_disabled_and_says_what_it_needs():
    (action,) = processingActions("root", "prefix", [NeedsThing], _noCallback)
    assert action.title == "Needs Thing… (needs Thing)"
    assert not action.enablement.eval({"image_count": 5})


def test_band_parameters_is_offered_under_spectral_parameters():
    (action,) = [a for a in ALL_ACTIONS if a.id == "varda.processing.band_parameters"]
    assert action.title.startswith("Band Parameters (HyPyRameter)…")
    assert action.menus[0].id == "varda/processing/spectral_parameters"
    assert ("varda/processing", "Spectral Parameters") in [
        (parent, item.title) for parent, item in PROCESSING_SUBMENUS
    ]
