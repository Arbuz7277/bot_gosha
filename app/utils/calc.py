"""Safe arithmetic evaluator for /answer (no eval, no numexpr)."""
from __future__ import annotations

import ast
import math
import operator

MAX_LENGTH = 200
MAX_EXPONENT = 1000
CONSTANTS = {"pi": math.pi, "e": math.e, "G": 6.67430e-11, "c": 299_792_458.0}


class CalcError(ValueError):
    """Raised for invalid or unsafe expressions."""


def _pow(base: float, exp: float) -> float:
    if abs(exp) > MAX_EXPONENT:
        raise CalcError("exponent is too large")
    try:
        return math.pow(base, exp)
    except (OverflowError, ValueError) as exc:
        raise CalcError("result is out of range") from exc


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        try:
            return _BINARY[type(node.op)](_eval(node.left), _eval(node.right))
        except ZeroDivisionError as exc:
            raise CalcError("division by zero") from exc
        except OverflowError as exc:
            raise CalcError("result is out of range") from exc
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise CalcError("unsupported expression")


def safe_calc(expression: str) -> float:
    expression = expression.strip().replace("^", "**")
    if not expression or len(expression) > MAX_LENGTH:
        raise CalcError("empty or too long expression")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalcError("invalid syntax") from exc
    result = _eval(tree)
    if not math.isfinite(result):
        raise CalcError("result is not finite")
    return result


def format_result(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"
