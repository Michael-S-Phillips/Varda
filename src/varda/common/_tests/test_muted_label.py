"""Secondary text stays legible on light and dark themes."""

from PyQt6.QtGui import QColor, QPalette

from varda.common.ui import MutedLabel, mutedTextColor


def _palette(text: str, window: str, mid: str) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Window, QColor(window))
    palette.setColor(QPalette.ColorRole.Mid, QColor(mid))
    return palette


def _contrast(a: QColor, b: QColor) -> float:
    def luminance(color: QColor) -> float:
        def channel(value: float) -> float:
            return (
                value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            )

        return (
            0.2126 * channel(color.redF())
            + 0.7152 * channel(color.greenF())
            + 0.0722 * channel(color.blueF())
        )

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# macOS's own colours: "mid" is nearly the window colour in dark mode
DARK = _palette("#ffffff", "#323232", "#3a3a3a")
LIGHT = _palette("#000000", "#ececec", "#b8b8b8")


def test_muted_text_is_legible_but_quieter_than_normal_text():
    for palette in (DARK, LIGHT):
        text = palette.color(QPalette.ColorRole.WindowText)
        window = palette.color(QPalette.ColorRole.Window)
        muted = mutedTextColor(palette)
        assert _contrast(muted, window) >= 4.5  # WCAG AA for body text
        assert _contrast(muted, window) < _contrast(text, window)


def test_the_label_follows_a_theme_change(qtbot, qapp):
    label = MutedLabel("hint")
    qtbot.addWidget(label)
    original = qapp.palette()
    try:
        for palette in (DARK, LIGHT):
            qapp.setPalette(palette)
            qtbot.waitUntil(
                lambda: label.palette().color(QPalette.ColorRole.WindowText)
                == mutedTextColor(palette)
            )
    finally:
        qapp.setPalette(original)
