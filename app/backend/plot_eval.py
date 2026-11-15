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


VIEW_MARGIN = 0.02  # fraction of the visible width added on each side of the view
EXTENSION_POINTS = 200  # samples per widening step; keeps the off-screen part cheap
MAX_WIDENINGS = 20  # per side
MAX_ABS_X = 1e6


@dataclass
class View2D:
    plot: Plot2D
    x_range: tuple[float, float]
    widenings: tuple[int, int]  # (left, right)


def _evaluate_all(exprs: list, x_name: str, xs: np.ndarray) -> list[np.ndarray]:
    return [evaluate_on_grid(expr, {x_name: xs}, xs.shape) for expr in exprs]


def _still_leaving(inner: float, edge: float, y_lo: float, y_hi: float) -> bool:
    """True if the curve, moving outward, is still heading toward the top or bottom of the view."""
    if not (np.isfinite(inner) and np.isfinite(edge)):
        return False
    if edge > inner:
        return edge < y_hi
    if edge < inner:
        return edge > y_lo
    return False


def _grow_side(exprs, x_name, edge, inner_vals, edge_vals, direction, first_step, y_lo, y_hi, max_steps):
    segments_x: list[np.ndarray] = []
    segments_y: list[list[np.ndarray]] = []
    step = first_step
    while (
        len(segments_x) < max_steps
        and abs(edge) < MAX_ABS_X
        and any(_still_leaving(i, e, y_lo, y_hi) for i, e in zip(inner_vals, edge_vals))
    ):
        new_edge = float(np.clip(edge + direction * step, -MAX_ABS_X, MAX_ABS_X))
        seg = np.linspace(edge, new_edge, EXTENSION_POINTS + 1)[1:]
        ys = _evaluate_all(exprs, x_name, seg)
        segments_x.append(seg)
        segments_y.append(ys)
        inner_vals = [y[-2] for y in ys]
        edge_vals = [y[-1] for y in ys]
        edge = new_edge
        step *= 2
    return segments_x, segments_y


def sample_view_2d(
    spec: dict,
    x_view: tuple[float, float],
    y_view: tuple[float, float],
    max_widenings: int = MAX_WIDENINGS,
) -> View2D:
    """Samples every 2D trace over the visible x range (plus a margin) for the given view.

    The visible range gets POINTS_2D samples. If a curve is still moving toward the top or
    bottom of the view at an edge, that side is widened (the distance doubles each step, at
    most ``max_widenings`` steps, never past MAX_ABS_X) with coarser samples, so the curve
    keeps going until it leaves the view vertically. The y view is only used for that check.
    """
    x_name, _ = variable_names(spec)
    traces = spec.get("traces") or []
    exprs = [t.get("expr") for t in traces]
    labels = [trace_label(t) for t in traces]
    x_lo, x_hi = sorted(float(v) for v in x_view)
    y_lo, y_hi = sorted(float(v) for v in y_view)
    pad = (x_hi - x_lo) * VIEW_MARGIN
    lo, hi = x_lo - pad, x_hi + pad
    first_step = max(hi - lo, 1.0)

    xs = linspace(lo, hi, POINTS_2D)
    ys = _evaluate_all(exprs, x_name, xs)
    left_x, left_y = _grow_side(
        exprs, x_name, lo,
        [y[1] for y in ys], [y[0] for y in ys],
        -1, first_step, y_lo, y_hi, max_widenings,
    )
    right_x, right_y = _grow_side(
        exprs, x_name, hi,
        [y[-2] for y in ys], [y[-1] for y in ys],
        1, first_step, y_lo, y_hi, max_widenings,
    )

    all_x = np.concatenate([xs, *left_x, *right_x])
    order = np.argsort(all_x, kind="stable")
    curves = []
    for i, label in enumerate(labels):
        parts = [ys[i], *(seg[i] for seg in left_y), *(seg[i] for seg in right_y)]
        curves.append(Curve(label, np.concatenate(parts)[order]))
    sorted_xs = all_x[order]
    return View2D(
        plot=Plot2D(xs=sorted_xs, curves=curves),
        x_range=(float(sorted_xs[0]), float(sorted_xs[-1])),
        widenings=(len(left_x), len(right_x)),
    )


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
