"""Render settings survive a session: bands, mode, stretch and color map."""

import json

import pyqtgraph as pg

from varda.common.vec2 import Vec2
from varda.image_rendering.image_renderer import RendererSettings, RenderMode
from varda.image_rendering.render_state import restoreSettings, settingsState
from varda.utilities.debug import generate_random_image


def test_settings_round_trip_through_json():
    image = generate_random_image((20, 20, 10))
    settings = RendererSettings(image)
    settings.mode.set(RenderMode.RGB)
    settings.rgb.red.set(7)
    settings.rgb.green.set(3)
    settings.rgb.blue.set(1)
    settings.mono.colorMap.set(pg.colormap.get("magma"))
    percentile = settings.stretch.option("Linear Percentile")
    percentile.config.lowPercent.set(5)
    settings.stretch.selectByName("Linear Percentile")
    manual = settings.stretch.option("Min-Max (Manual)")
    manual.config.greenStretch.set(Vec2(0.1, 0.9))

    state = json.loads(json.dumps(settingsState(settings)))
    restored = RendererSettings(image)
    changes = []
    restored.sigParameterChanged.connect(lambda *_: changes.append(1))
    restoreSettings(restored, state)

    assert restored.mode.get() == RenderMode.RGB
    assert (
        restored.rgb.red.get(),
        restored.rgb.green.get(),
        restored.rgb.blue.get(),
    ) == (7, 3, 1)
    assert restored.stretch.nameOf(restored.stretch.current) == "Linear Percentile"
    assert restored.stretch.option("Linear Percentile").config.lowPercent.get() == 5
    assert restored.stretch.option(
        "Min-Max (Manual)"
    ).config.greenStretch.get() == Vec2(0.1, 0.9)
    lut = restored.mono.colorMap.get().getLookupTable(0, 1, 2)
    assert tuple(lut[-1][:3]) == tuple(
        pg.colormap.get("magma").getLookupTable(0, 1, 2)[-1][:3]
    )
    assert len(changes) == 1  # announced once


def test_bands_an_image_lacks_are_skipped():
    big = RendererSettings(generate_random_image((20, 20, 10)))
    big.mono.band.set(9)
    small = RendererSettings(generate_random_image((20, 20, 10)))
    state = settingsState(big)
    state["mono"]["band"] = 42  # a session for a bigger image
    restoreSettings(small, state)
    assert small.mono.band.get() < 10
