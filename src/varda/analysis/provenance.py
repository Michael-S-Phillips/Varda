"""How a result was made: the analysis, its parameters, its inputs, the Varda
version and the time, kept in the result's metadata and written into the
description of an exported file."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

import numpy as np
from PyQt6.QtGui import QColor

from varda.analysis.analysis import Analysis
from varda.common.entities import VardaRaster
from varda.common.parameter import Parameter, ParameterGroup
from varda.common.provenance import PROVENANCE_KEY
from varda.common.provenance import provenanceText as provenanceText
from varda.version import vardaVersion


def _plain(value):
    """A parameter value as JSON-friendly data."""
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, VardaRaster):
        return value.name
    if isinstance(value, QColor):
        return value.name()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def parameterValues(group: ParameterGroup) -> dict:
    values = {}
    for param in group.params.values():
        if isinstance(param, ParameterGroup):
            values[type(param).__name__] = parameterValues(param)
        elif isinstance(param, Parameter):
            values[param.name] = _plain(param.get())
    return values


def recordProvenance(
    result: VardaRaster, analysis: Analysis, image: VardaRaster
) -> None:
    result.extraMetadata[PROVENANCE_KEY] = {
        "analysis": analysis.name,
        "analysisId": analysis.analysisId,
        "parameters": parameterValues(analysis),
        "inputs": [{"name": image.name, "path": image.filePath}],
        "vardaVersion": vardaVersion(),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
