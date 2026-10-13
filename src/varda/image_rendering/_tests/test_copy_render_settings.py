"""Display settings copy over, including the stretch and its own settings."""

from varda.common.parameter import Vec2Parameter, copyValues
from varda.common.vec2 import Vec2
from varda.image_rendering.image_renderer import RenderMode, RendererSettings
from varda.image_rendering.render_parameters import StretchParameter
from varda.utilities.debug import generate_random_image


def _redStretch(settings: RendererSettings) -> Vec2Parameter:
    manual = settings.stretch.option(StretchParameter.MANUAL_NAME).parameters()
    param = manual.params["redStretch"]
    assert isinstance(param, Vec2Parameter)
    return param


def test_bands_mode_and_stretch_are_copied(qapp):
    image = generate_random_image((10, 10, 10))
    source, target = RendererSettings(image), RendererSettings(image)
    source.mode.set(RenderMode.RGB)
    source.rgb.red.set(7)
    source.stretch.selectByName(StretchParameter.MANUAL_NAME)
    _redStretch(source).set(Vec2(0.1, 0.4))

    copyValues(source, target)

    assert target.mode.get() is RenderMode.RGB
    assert target.rgb.red.get() == 7
    assert target.stretch.nameOf(target.stretch.current) == StretchParameter.MANUAL_NAME
    copied = _redStretch(target).get()
    assert (copied.x, copied.y) == (0.1, 0.4)
    assert target.stretch.current is not source.stretch.current  # its own instance
