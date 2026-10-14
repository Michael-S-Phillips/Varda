import pytest

from varda.kindling.categories import duplicateOf, menuCategories

EXISTING = menuCategories()


def test_varda_categories_come_in_menu_order():
    assert EXISTING[:2] == ["Spectral Parameters", "Filtering"]
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
    assert duplicateOf(category, EXISTING) == duplicate
