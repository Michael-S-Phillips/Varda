"""Distinct colours for categories: ROI classes and the classes of a class map."""

CLASS_PALETTE = [
    "#e6194b",  # red
    "#3cb44b",  # green
    "#4363d8",  # blue
    "#ffe119",  # yellow
    "#f58231",  # orange
    "#911eb4",  # purple
    "#42d4f4",  # cyan
    "#f032e6",  # magenta
    "#bfef45",  # lime
    "#9a6324",  # brown
    "#469990",  # teal
    "#dcbeff",  # lavender
]


def classColor(index: int) -> str:
    return CLASS_PALETTE[index % len(CLASS_PALETTE)]
