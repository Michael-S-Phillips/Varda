"""Isolated CRISM geometry (DDR backplane) support for column-locked ROI placement.

CRISM reflectance products ship a separate geometry "DDR" file whose bands give,
per pixel, the detector column ("IR Sample") and the source strip identity
("Target ID" + "Segment ID"). This module resolves that companion file and
computes the horizontal shift needed to place a copied ROI on the same detector
column as its template. It is deliberately CRISM-specific and self-contained: no
general multi-instrument abstraction until a second instrument needs one.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

# (pattern, replacement) applied to the filename stem to find the DDR companion.
_GEOMETRY_NAME_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"_mrr(al|if|ir|sr|su|ra)_", re.IGNORECASE), "_mrrde_"),
    (re.compile(r"_vrr(al|if|ir|sr|su|ra)_", re.IGNORECASE), "_vrrde_"),
    (re.compile(r"_(if|sr|su)(\d{3}[a-z])", re.IGNORECASE), r"_in\2"),
]


def resolveGeometryFile(sourceFilename: str) -> str | None:
    """Map a CRISM source ``.img``/``.hdr`` path to its geometry companion path.

    Returns the companion ``.img`` path if it exists on disk, else None.
    """
    directory = os.path.dirname(sourceFilename)
    filename = os.path.basename(sourceFilename)
    stem, _ext = os.path.splitext(filename)

    for pattern, replacement in _GEOMETRY_NAME_PATTERNS:
        newStem, nSubs = pattern.subn(replacement, stem)
        if nSubs == 0 or newStem == stem:
            continue
        candidate = os.path.join(directory, newStem + ".img")
        if os.path.exists(candidate):
            return candidate
    return None
