"""Calculated ROI columns.

A column can be filled from each ROI's geometry (area, perimeter, centroid),
from a statistic of a raster band inside the ROI (zonal statistics), or from
an expression over other columns. ``CalculatedColumns`` keeps them current as
ROIs are drawn or edited. Expressions are parsed and evaluated by a small
whitelisting evaluator, never ``eval``.
"""

from __future__ import annotations

import ast
import math
import operator
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from pyproj import CRS
from shapely.geometry import Polygon

from varda.common.entities import VardaRaster
from varda.rois.roi_collection import ROICollection

# kind -> (label, short name used in suggested column names)
GEOMETRY_MEASURES = {
    "area_pixels": ("Area (pixels)", "area_px"),
    "perimeter_pixels": ("Perimeter (pixels)", "perimeter_px"),
    "area_map": ("Area (map units²)", "area"),
    "perimeter_map": ("Perimeter (map units)", "perimeter"),
    "centroid_x": ("Centroid x (map units)", "centroid_x"),
    "centroid_y": ("Centroid y (map units)", "centroid_y"),
}
MAP_MEASURES = {"area_map", "perimeter_map", "centroid_x", "centroid_y"}


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


STATISTICS: dict[str, Callable[[np.ndarray], float]] = {
    "mean": lambda v: float(np.mean(v)),
    "median": lambda v: float(np.median(v)),
    "std": lambda v: float(np.std(v)),
    "min": lambda v: float(np.min(v)),
    "max": lambda v: float(np.max(v)),
    "sum": lambda v: float(np.sum(v)),
    "count": lambda v: float(v.size),
}

FUNCTIONS: dict[str, Callable[..., float]] = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
}
CONSTANTS = {"pi": math.pi, "e": math.e}
_OPERATORS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


@dataclass(frozen=True)
class GeometryMeasure:
    kind: str  # a key of GEOMETRY_MEASURES


@dataclass(frozen=True)
class ZonalStatistic:
    image: VardaRaster
    band: int
    statistic: str  # a key of STATISTICS


@dataclass(frozen=True)
class Expression:
    text: str


Calculation = GeometryMeasure | ZonalStatistic | Expression


class ExpressionError(ValueError):
    pass


def _words(text: str) -> str:
    """Spaces and symbols become ``_``; NFKC-normalised as Python normalises
    identifiers (e.g. the micro sign µ becomes Greek μ)."""
    return re.sub(r"\W+", "_", unicodedata.normalize("NFKC", text)).strip("_")


def identifier(column: str) -> str:
    """How a column is named in expressions."""
    name = _words(column)
    return f"_{name}" if name[:1].isdigit() else name


def expressionVariables(collection: ROICollection) -> dict[str, str]:
    """Expression name -> column, for every user column."""
    return {identifier(c): c for c in collection.userColumns}


def parseExpression(text: str, variables: set[str]) -> ast.Expression:
    """Parse and check an expression; raises ExpressionError with the reason."""
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as error:
        raise ExpressionError(f"syntax error: {error.msg}") from error
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else "this call"
            if name not in FUNCTIONS or node.keywords:
                raise ExpressionError(f"function {name} is not allowed")
        elif isinstance(node, ast.Name):
            if (
                node.id not in variables
                and node.id not in FUNCTIONS
                and node.id not in CONSTANTS
            ):
                raise ExpressionError(f"unknown column '{node.id}'")
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, int | float):
                raise ExpressionError("only numbers are allowed")
        elif not isinstance(
            node,
            ast.Expression
            | ast.BinOp
            | ast.UnaryOp
            | ast.Load
            | ast.operator
            | ast.unaryop,
        ):
            raise ExpressionError(f"{type(node).__name__} is not allowed")
        if (
            isinstance(node, ast.BinOp | ast.UnaryOp)
            and type(node.op) not in _OPERATORS
        ):
            raise ExpressionError(f"{type(node.op).__name__} is not allowed")
    return tree


def _evaluate(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Constant):
        value = node.value
        assert isinstance(value, int | float)  # parseExpression allows only numbers
        return float(value)
    if isinstance(node, ast.Name):
        return values[node.id] if node.id in values else CONSTANTS[node.id]
    if isinstance(node, ast.BinOp):
        return _OPERATORS[type(node.op)](
            _evaluate(node.left, values), _evaluate(node.right, values)
        )
    if isinstance(node, ast.UnaryOp):
        return _OPERATORS[type(node.op)](_evaluate(node.operand, values))
    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)
        return float(
            FUNCTIONS[node.func.id](*[_evaluate(a, values) for a in node.args])
        )
    raise ExpressionError(f"{type(node).__name__} is not allowed")


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def mapUnits(collection: ROICollection) -> str | None:
    """The collection's linear unit (e.g. "metre"), or None in pixel space."""
    crs = collection.crs
    if crs is None:
        return None
    axes = CRS.from_user_input(crs).axis_info  # rasterio or pyproj CRS
    return axes[0].unit_name if axes else "units"


def suggestName(calculation: Calculation, units: str | None = None) -> str:
    if isinstance(calculation, GeometryMeasure):
        short = GEOMETRY_MEASURES[calculation.kind][1]
        if calculation.kind in ("area_map", "perimeter_map") and units in (
            "metre",
            "meter",
        ):
            return f"{short}_m2" if calculation.kind == "area_map" else f"{short}_m"
        return short
    if isinstance(calculation, ZonalStatistic):
        band = _words(str(calculation.image.bandNames[calculation.band])).lower()
        return f"{calculation.statistic}_{band[:20]}"
    return "calc"


def describe(calculation: Calculation) -> str:
    if isinstance(calculation, GeometryMeasure):
        return GEOMETRY_MEASURES[calculation.kind][0]
    if isinstance(calculation, ZonalStatistic):
        band = calculation.image.bandNames[calculation.band]
        return f"{calculation.statistic} of {band} in {calculation.image.name}"
    return f"= {calculation.text}"


class CalculatedColumns:
    """The collection's calculated columns, recalculated as ROIs change."""

    def __init__(self, collection: ROICollection):
        self.collection = collection
        self._columns: dict[str, Calculation] = {}
        self._updating = False
        collection.sigROIAdded.connect(self._onROIChanged)
        collection.sigROIUpdated.connect(self._onROIChanged)
        collection.sigColumnsChanged.connect(self._onColumnsChanged)

    def add(self, name: str, calculation: Calculation) -> str:
        """Add a calculated column; returns its name as stored."""
        if isinstance(calculation, Expression):
            parseExpression(calculation.text, set(expressionVariables(self.collection)))
        self.collection.addColumn(name)
        column = name.strip().lower()
        self._columns[column] = calculation
        self.recalculate(columns=[column])
        return column

    def isCalculated(self, column: str) -> bool:
        return column in self._columns

    def describe(self, column: str) -> str | None:
        calculation = self._columns.get(column)
        return describe(calculation) if calculation is not None else None

    def preview(self, calculation: Calculation) -> float | None:
        """The value for the first ROI, without adding a column."""
        fids = self.collection.fids
        return self._values(calculation, fids[:1])[0] if fids else None

    def recalculate(
        self, columns: Sequence[str] | None = None, fids: Sequence[int] | None = None
    ) -> None:
        fids = list(self.collection.fids if fids is None else fids)
        names = [c for c in self._columns if columns is None or c in columns]
        self._updating = True
        try:
            for column in names:  # in the order added, so expressions see earlier ones
                for fid, value in zip(fids, self._values(self._columns[column], fids)):
                    self.collection.setProperty(fid, column, value)
        finally:
            self._updating = False

    # --- internals -----------------------------------------------------------

    def _values(self, calculation: Calculation, fids: Sequence[int]) -> list[float]:
        if isinstance(calculation, GeometryMeasure):
            return [self._geometry(calculation.kind, fid) for fid in fids]
        if isinstance(calculation, ZonalStatistic):
            return self._zonal(calculation, fids)
        tree = parseExpression(
            calculation.text, set(expressionVariables(self.collection))
        )
        variables = expressionVariables(self.collection)
        results = []
        for fid in fids:
            values = {
                name: _number(self.collection.getProperty(fid, column))
                for name, column in variables.items()
            }
            try:
                results.append(float(_evaluate(tree, values)))
            except (ArithmeticError, ValueError):
                results.append(math.nan)
        return results

    def _geometry(self, kind: str, fid: int) -> float:
        if kind in MAP_MEASURES and self.collection.crs is not None:
            shape = self.collection.getROI(fid).geometry
        else:
            shape = Polygon(self.collection.getPixelCoordinates(fid))
        if kind.startswith("area"):
            return float(shape.area)
        if kind.startswith("perimeter"):
            return float(shape.length)
        centroid = shape.centroid
        return float(centroid.x if kind == "centroid_x" else centroid.y)

    def _zonal(self, calculation: ZonalStatistic, fids: Sequence[int]) -> list[float]:
        raw = calculation.image.getBands([calculation.band])
        band = np.ma.filled(np.ma.asarray(raw, dtype=np.float64), np.nan)[:, :, 0]
        statistic = STATISTICS[calculation.statistic]
        results = []
        for fid in fids:
            values = _finite(band[self.collection.getMask(fid, calculation.image)])
            empty = values.size == 0 and calculation.statistic != "count"
            results.append(math.nan if empty else statistic(values))
        return results

    def _onROIChanged(self, fid: int) -> None:
        if not self._updating and self._columns:
            self.recalculate(fids=[fid])

    def _onColumnsChanged(self) -> None:
        present = set(self.collection.userColumns)
        self._columns = {c: k for c, k in self._columns.items() if c in present}
