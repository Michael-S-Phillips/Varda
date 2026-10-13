"""A small, safe expression language for user-typed formulas.

Expressions are parsed with ``ast`` and checked against a whitelist (numbers,
names the caller allows, arithmetic, and the caller's functions; comparisons
when asked for), then evaluated by walking the tree -- never ``eval``. The
same evaluator works on numbers (calculated ROI columns) and on numpy arrays
(band math), depending on the functions supplied.
"""

from __future__ import annotations

import ast
import operator
import re
import unicodedata
from collections.abc import Callable, Mapping

OPERATORS: dict[type, Callable] = {
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
COMPARISONS: dict[type, Callable] = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


class ExpressionError(ValueError):
    pass


def words(text: str) -> str:
    """Spaces and symbols become ``_``; NFKC-normalized as Python normalizes
    identifiers (e.g. the micro sign µ becomes Greek μ)."""
    return re.sub(r"\W+", "_", unicodedata.normalize("NFKC", text)).strip("_")


def identifier(name: str) -> str:
    """How an arbitrary name (a column, a band) is written in an expression."""
    text = words(name)
    return f"_{text}" if text[:1].isdigit() else text


def parse(
    text: str,
    isVariable: Callable[[str], bool],
    functions: Mapping[str, Callable],
    constants: Mapping[str, float],
    *,
    comparisons: bool = False,
    unknownName: str = "unknown name '{}'",
) -> ast.Expression:
    """Parse and check ``text``; raises ExpressionError with the reason."""
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as error:
        raise ExpressionError(f"syntax error: {error.msg}") from error
    allowed: tuple[type, ...] = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Load,
        ast.operator,
        ast.unaryop,
    )
    if comparisons:
        allowed += (ast.Compare, ast.cmpop)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else "this call"
            if name not in functions or node.keywords:
                raise ExpressionError(f"function {name} is not allowed")
        elif isinstance(node, ast.Name):
            if not (
                isVariable(node.id) or node.id in functions or node.id in constants
            ):
                raise ExpressionError(unknownName.format(node.id))
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, int | float) or isinstance(node.value, bool):
                raise ExpressionError("only numbers are allowed")
        elif not isinstance(node, allowed):
            raise ExpressionError(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.BinOp | ast.UnaryOp) and type(node.op) not in OPERATORS:
            raise ExpressionError(f"{type(node.op).__name__} is not allowed")
        if isinstance(node, ast.Compare) and len(node.ops) != 1:
            raise ExpressionError("chained comparisons are not allowed; use where()")
    return tree


def evaluate(
    tree: ast.AST,
    values: Mapping,
    functions: Mapping[str, Callable],
    constants: Mapping[str, float],
):
    """The value of a tree from ``parse`` (numbers or numpy arrays)."""

    def walk(node: ast.AST):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            value = node.value
            assert isinstance(value, int | float)  # parse allows only numbers
            return float(value)
        if isinstance(node, ast.Name):
            return values[node.id] if node.id in values else constants[node.id]
        if isinstance(node, ast.BinOp):
            return OPERATORS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp):
            return OPERATORS[type(node.op)](walk(node.operand))
        if isinstance(node, ast.Compare):
            return COMPARISONS[type(node.ops[0])](
                walk(node.left), walk(node.comparators[0])
            )
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name)
            return functions[node.func.id](*[walk(a) for a in node.args])
        raise ExpressionError(f"{type(node).__name__} is not allowed")

    return walk(tree)
