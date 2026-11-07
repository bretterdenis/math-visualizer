"""Evaluates mathjs-style expressions on plot grids with numpy.

Expressions are never passed to Python's eval(). They are tokenized, translated to Python
syntax (``^`` -> ``**``, implicit multiplication such as ``2x`` -> ``2*x``), parsed with
``ast``, and then walked by a small evaluator that only allows whitelisted names, operators
and functions. Any invalid, unknown or failing evaluation yields NaN, which matplotlib leaves
as a gap, mirroring the former ``safeEval`` in plot-math.js.
"""

from __future__ import annotations

import ast
import functools
import operator
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

POINTS_2D = 800
POINTS_3D = 80
SURFACE_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#59a14f", "#b07aa1", "#76b7b2"]


class ExpressionError(ValueError):
    """The expression is not valid or uses something unsupported."""


# ---------------------------------------------------------------- translation

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<op>\*\*|\^|[-+*/%(),])"
    r")"
)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    text = expr.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ExpressionError(f"Unexpected character at position {pos}")
        pos = m.end()
        kind = m.lastgroup
        tokens.append((kind, m.group(kind)))
    return tokens


def _ends_operand(tok: tuple[str, str]) -> bool:
    return tok[0] in ("num", "name") or tok == ("op", ")")


def _starts_operand(tok: tuple[str, str]) -> bool:
    return tok[0] in ("num", "name") or tok == ("op", "(")


def translate(expr: str) -> str:
    """Translates mathjs syntax to Python syntax (without evaluating it)."""
    tokens = _tokenize(expr)
    pieces: list[str] = []
    prev: Optional[tuple[str, str]] = None
    for tok in tokens:
        if prev is not None and _ends_operand(prev) and _starts_operand(tok):
            # ``name(`` is a function call, so no implicit multiplication there.
            if not (prev[0] == "name" and tok == ("op", "(")):
                pieces.append("*")
        pieces.append("**" if tok == ("op", "^") else tok[1])
        prev = tok
    return "".join(pieces)


def compile_expression(expr: str) -> ast.Expression:
    if not isinstance(expr, str) or not expr.strip():
        raise ExpressionError("Empty expression")
    try:
        return ast.parse(translate(expr), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(str(exc)) from exc


# ---------------------------------------------------------------- evaluation

def _min(*args):
    return functools.reduce(np.minimum, args)


def _max(*args):
    return functools.reduce(np.maximum, args)


def _log(x, base=None):
    return np.log(x) if base is None else np.log(x) / np.log(base)


FUNCTIONS: dict[str, Callable] = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan, "atan2": np.arctan2,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "asinh": np.arcsinh, "acosh": np.arccosh, "atanh": np.arctanh,
    "sec": lambda x: 1 / np.cos(x), "csc": lambda x: 1 / np.sin(x), "cot": lambda x: 1 / np.tan(x),
    "exp": np.exp, "log": _log, "log10": np.log10, "log2": np.log2, "log1p": np.log1p,
    "sqrt": np.sqrt, "cbrt": np.cbrt, "abs": np.abs, "sign": np.sign,
    "floor": np.floor, "ceil": np.ceil, "round": np.round, "fix": np.trunc,
    "pow": np.power, "mod": np.mod, "hypot": np.hypot,
    "min": _min, "max": _max, "square": np.square, "cube": lambda x: x * x * x,
}

CONSTANTS: dict[str, float] = {
    "pi": np.pi, "e": np.e, "E": np.e, "tau": 2 * np.pi, "phi": (1 + np.sqrt(5)) / 2,
}

_BIN_OPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: np.power,
    ast.Mod: np.mod,
}
_UNARY_OPS: dict[type, Callable] = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval_node(node: ast.AST, env: dict[str, np.ndarray]):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return np.float64(node.value)
        raise ExpressionError("Unsupported literal")
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        if node.id in CONSTANTS:
            return np.float64(CONSTANTS[node.id])
        raise ExpressionError(f"Unknown symbol '{node.id}'")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left, env), _eval_node(node.right, env))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, env))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        func = FUNCTIONS.get(node.func.id)
        if func is None:
            raise ExpressionError(f"Unknown function '{node.func.id}'")
        return func(*[_eval_node(arg, env) for arg in node.args])
    raise ExpressionError("Unsupported syntax")


def evaluate_on_grid(expr: str, scope: dict[str, np.ndarray], shape: tuple) -> np.ndarray:
    """Evaluates ``expr`` with variables bound to arrays of ``shape``.

    Returns a float array of ``shape``. Invalid expressions, failing evaluations, complex
    results and non-finite values all become NaN.
    """
    nan_grid = np.full(shape, np.nan)
    try:
        node = compile_expression(expr)
        env = {name: np.asarray(value, dtype=float) for name, value in scope.items()}
        with np.errstate(all="ignore"):
            value = _eval_node(node, env)
            value = np.asarray(value)
            if np.iscomplexobj(value):
                return nan_grid
            out = np.array(np.broadcast_to(value, shape), dtype=float)
        out[~np.isfinite(out)] = np.nan
        return out
    except Exception:  # mirrors safeEval: never throw, degrade to NaN
        return nan_grid


def evaluate_scalar(expr: str, scope: dict[str, float]) -> float:
    """Convenience wrapper: one point. Returns NaN on any failure."""
    result = evaluate_on_grid(expr, {k: np.asarray(v, dtype=float) for k, v in scope.items()}, ())
    return float(result)


# ---------------------------------------------------------------- plot data

def linspace(lo: float, hi: float, n: int) -> np.ndarray:
    return np.linspace(lo, hi, n)


def _or(value, default):
    return default if value is None else value


def variable_names(spec: dict) -> tuple[str, str]:
    variables = spec.get("variables") or ["x"]
    x_name = variables[0] or "x"
    y_name = (variables[1] if len(variables) > 1 else None) or "y"
    return x_name, y_name


def domain_bounds(spec: dict) -> tuple[float, float, float, float]:
    domain = spec.get("domain") or {}
    x_min = _or(domain.get("xMin"), -10)
    x_max = _or(domain.get("xMax"), 10)
    y_min = _or(domain.get("yMin"), x_min)
    y_max = _or(domain.get("yMax"), x_max)
    return x_min, x_max, y_min, y_max


def trace_label(trace: dict) -> str:
    return trace.get("label") or trace.get("expr") or ""


@dataclass
class Curve:
    label: str
    ys: np.ndarray


@dataclass
class Plot2D:
    xs: np.ndarray
    curves: list[Curve] = field(default_factory=list)


@dataclass
class Surface:
    label: str
    zs: np.ndarray
    color: str


@dataclass
class Plot3D:
    X: np.ndarray
    Y: np.ndarray
    surfaces: list[Surface] = field(default_factory=list)


def compute_2d(spec: dict) -> Plot2D:
    x_name, _ = variable_names(spec)
    x_min, x_max, _, _ = domain_bounds(spec)
    xs = linspace(x_min, x_max, POINTS_2D)
    curves = [
        Curve(trace_label(t), evaluate_on_grid(t.get("expr"), {x_name: xs}, xs.shape))
        for t in (spec.get("traces") or [])
    ]
    return Plot2D(xs=xs, curves=curves)


def compute_3d(spec: dict) -> Plot3D:
    x_name, y_name = variable_names(spec)
    x_min, x_max, y_min, y_max = domain_bounds(spec)
    xs = linspace(x_min, x_max, POINTS_3D)
    ys = linspace(y_min, y_max, POINTS_3D)
    X, Y = np.meshgrid(xs, ys)
    traces = spec.get("traces") or [{"expr": "0"}]
    surfaces = []
    for i, trace in enumerate(traces):
        zs = evaluate_on_grid(trace.get("expr"), {x_name: X, y_name: Y}, X.shape)
        surfaces.append(Surface(trace_label(trace), zs, SURFACE_COLORS[i % len(SURFACE_COLORS)]))
    return Plot3D(X=X, Y=Y, surfaces=surfaces)
