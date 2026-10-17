import pytest

from varda.kindling.categories import duplicateOf, menuCategories, placementProblem

EXISTING = menuCategories()
FLAT = [
    "Spectral Parameters",
    "Filtering",
    "Statistics",
    "Derivatives",
    "Classification",
]


def test_varda_categories_come_in_menu_order_as_paths():
    assert EXISTING[:4] == [
        "Spectral Parameters",
        "Image Math",  # beside Band Math
        "Filtering/Spatial",
        "Filtering/Spectral",
    ]
    assert "Target Detection" in EXISTING


@pytest.mark.parametrize(
    ("category", "duplicate"),
    [
        ("Filtering", ""),  # exactly an existing one
        ("Filters", "Filtering"),
        ("filtering", "Filtering"),
        ("Filter", "Filtering"),
        ("Statistical", "Statistics"),
        ("Derivative", "Derivatives"),
        ("Spectral Parameter", "Spectral Parameters"),
        ("Classifiers", "Classification"),
        ("Mosaicking", ""),  # genuinely new
        ("Texture", ""),
        ("Spectral Indices", ""),
    ],
)
def test_near_duplicate_categories(category, duplicate):
    assert duplicateOf(category, FLAT) == duplicate


@pytest.mark.parametrize("category", ["Filtering", "Filters", "filtering"])
def test_a_menu_with_submenus_asks_for_one_of_them(category):
    problem = placementProblem("Smoothing", category, EXISTING)
    assert "'Filtering/Spatial', 'Filtering/Spectral'" in problem


@pytest.mark.parametrize(
    "category", ["Filtering/Spatial", "Filtering/Spectral", "Mosaicking"]
)
def test_an_existing_submenu_or_a_new_menu_is_fine(category):
    assert placementProblem("X", category, EXISTING) == ""


def test_a_near_duplicate_leaf_category_names_the_existing_one():
    assert "set category = 'Statistics'" in placementProblem(
        "X", "Statistical", EXISTING
    )
