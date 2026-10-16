"""Render settings (bands, stretch, color map) as plain data for sessions,
and back. Unknown or unusable entries are skipped, so a session from an
older Varda, or for an image with fewer bands, still opens."""

from __future__ import annotations

import logging

import numpy as np
import pyqtgraph as pg

from varda.common.parameter import (
    BoolParameter,
    EnumParameter,
    FloatParameter,
    IntParameter,
    Parameter,
    ParameterGroup,
    StringParameter,
    Vec2Parameter,
)
from varda.common.vec2 import Vec2
from varda.image_rendering.render_parameters import (
    BandParameter,
    ColorMapParameter,
    StretchParameter,
)

logger = logging.getLogger(__name__)
PLAIN = (IntParameter, FloatParameter, BoolParameter, StringParameter)


def _value(param: Parameter) -> object:
    if isinstance(param, StretchParameter):
        return {
            "active": param.nameOf(param.current),
            "options": {
                name: settingsState(group) for name, group in param.optionGroups.items()
            },
        }
    if isinstance(param, ColorMapParameter):
        positions, colors = param.get().getStops()
        return {
            "positions": np.asarray(positions, float).tolist(),
            "colors": np.asarray(colors).tolist(),
        }
    if isinstance(param, EnumParameter):
        return param.get().name
    if isinstance(param, Vec2Parameter):
        value = param.get()
        return [float(value.x), float(value.y)]
    if isinstance(param, (BandParameter, *PLAIN)):
        return param.get()
    return None  # not saved (e.g. images)


def settingsState(group: ParameterGroup) -> dict:
    """A group's values as JSON-able data, nested groups included."""
    state = {}
    for name, param in group.params.items():
        if isinstance(param, ParameterGroup):
            state[name] = settingsState(param)
        else:
            value = _value(param)
            if value is not None:
                state[name] = value
    return state


def _restore(param: Parameter, value: object) -> None:
    if isinstance(param, StretchParameter) and isinstance(value, dict):
        for name, saved in value.get("options", {}).items():
            group = param.optionGroups.get(name)
            if group is not None:
                _restoreGroup(group, saved)
        if value.get("active") in param.optionNames:
            param.selectByName(value["active"])
    elif isinstance(param, ColorMapParameter) and isinstance(value, dict):
        param.set(
            pg.ColorMap(value["positions"], np.asarray(value["colors"], np.ubyte))
        )
    elif isinstance(param, EnumParameter):
        param.set(param.enumType[value])
    elif isinstance(param, Vec2Parameter):
        x, y = value  # type: ignore[misc]
        param.set(Vec2(float(x), float(y)))
    elif isinstance(param, BandParameter):
        band = int(value)  # type: ignore[arg-type]
        if param.image is None or 0 <= band < param.image.bandCount:
            param.set(band)
    elif isinstance(param, PLAIN):
        param.set(value)


def _restoreGroup(group: ParameterGroup, state: dict) -> None:
    for name, value in state.items():
        param = group.params.get(name)
        if param is None:
            continue
        try:
            if isinstance(param, ParameterGroup):
                _restoreGroup(param, value)
            else:
                _restore(param, value)
        except (KeyError, TypeError, ValueError) as error:
            logger.warning("Skipped the saved setting %s: %s", name, error)


def restoreSettings(group: ParameterGroup, state: dict) -> None:
    """Give a group the values ``settingsState`` saved; it announces the
    change once."""
    with group.sigParameterChanged.blocked():
        _restoreGroup(group, state)
    group.sigParameterChanged.emit(group)
