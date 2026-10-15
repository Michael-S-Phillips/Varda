"""The collection picker groups collections by body and mission, and a
search keeps those holding every word typed."""

from PyQt6.QtCore import Qt

from varda.catalogs.catalog import Collection
from varda.workspaces.find_data.collection_picker import (
    INDEX_ROLE,
    CollectionCombo,
)

COLLECTIONS = [
    Collection(
        "mars:MRO:CRISM:MTRDR",
        "MRO CRISM PDS4 Map-Projected Targeted Reduced Data Records",
        "Mars",
        "Compact Reconnaissance Imaging Spectrometer for Mars",
        "MRO CRISM",
    ),
    Collection(
        "mars:MRO:CTX:EDR",
        "MRO CTX Experiment Data Record",
        "Mars",
        "Context Camera",
        "MRO CTX",
    ),
    Collection(
        "moon:LRO:LROC:EDR",
        "LRO LROC Experiment Data Record",
        "Moon",
        "Lunar Reconnaissance Orbiter Camera",
        "LRO LROC",
    ),
    Collection("api#kaguya_dtms", "Kaguya Terrain Camera DTMs", "Moon"),
]


def _combo(qtbot) -> CollectionCombo:
    combo = CollectionCombo()
    qtbot.addWidget(combo)
    combo.setCollections(COLLECTIONS, select="mars:MRO:CTX:EDR")
    combo.show()
    combo.showPopup()
    assert combo.popup is not None
    return combo


def _shown(popup) -> list[str]:
    return [COLLECTIONS[i.data(INDEX_ROLE)].id for i in popup._leaves()]


def test_collections_are_grouped_by_body_then_mission(qtbot):
    combo = _combo(qtbot)
    assert combo.currentData() == "mars:MRO:CTX:EDR"
    popup = combo.popup
    model = popup.model
    bodies = [model.item(r).text() for r in range(model.rowCount())]
    assert bodies == ["Mars (2)", "Moon (2)"]
    mars = model.item(0)
    assert [mars.child(r).text() for r in range(mars.rowCount())] == [
        "MRO CRISM (1)",
        "MRO CTX (1)",
    ]
    # the group's name isn't repeated in the title
    assert mars.child(0).child(0).text().startswith("PDS4 Map-Projected")
    moon = model.item(1)  # an ungrouped collection sits under its body
    assert "Kaguya Terrain Camera DTMs" in [
        moon.child(r).text() for r in range(moon.rowCount())
    ]
    assert popup.count.text() == "4 collections"


def test_every_word_must_match_body_mission_instrument_or_title(qtbot):
    combo = _combo(qtbot)  # held: the popup is the combo's child
    popup = combo.popup
    popup.search.setText("mars crism")
    assert _shown(popup) == ["mars:MRO:CRISM:MTRDR"]
    popup.search.setText("moon")
    assert _shown(popup) == ["moon:LRO:LROC:EDR", "api#kaguya_dtms"]
    popup.search.setText("reconnaissance")  # in the instrument's description
    assert _shown(popup) == ["mars:MRO:CRISM:MTRDR", "moon:LRO:LROC:EDR"]
    assert popup.count.text() == "2 of 4 collections"


def test_enter_chooses_the_first_match(qtbot):
    combo = _combo(qtbot)
    with qtbot.waitSignal(combo.currentIndexChanged):
        combo.popup.search.setText("kaguya")
        qtbot.keyClick(combo.popup.search, Qt.Key.Key_Return)
    assert combo.currentData() == "api#kaguya_dtms"
