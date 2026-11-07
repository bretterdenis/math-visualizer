"""Expression translation, NaN handling and grid evaluation (port of plot-math.test.js)."""

import math
import unittest

import numpy as np

from app.backend.plot_eval import (
    ExpressionError,
    compute_2d,
    compute_3d,
    compile_expression,
    evaluate_on_grid,
    evaluate_scalar,
    linspace,
    translate,
    POINTS_2D,
    POINTS_3D,
    SURFACE_COLORS,
)


class LinspaceTests(unittest.TestCase):
    def test_endpoints_are_exact(self):
        xs = linspace(-10, 10, 5)
        self.assertEqual(xs[0], -10)
        self.assertEqual(xs[-1], 10)

    def test_returns_requested_count(self):
        self.assertEqual(len(linspace(0, 1, 11)), 11)

    def test_evenly_spaced(self):
        xs = linspace(0, 10, 6)
        self.assertTrue(np.allclose(np.diff(xs), 2))

    def test_single_point_returns_min(self):
        self.assertEqual(list(linspace(3, 7, 1)), [3.0])


class TranslationTests(unittest.TestCase):
    def test_caret_becomes_power(self):
        self.assertEqual(translate("x^2"), "x**2")

    def test_implicit_multiplication_number_symbol(self):
        self.assertEqual(translate("2x^2"), "2*x**2")

    def test_implicit_multiplication_before_parenthesis(self):
        self.assertEqual(translate("2(x+1)"), "2*(x+1)")

    def test_function_call_is_not_multiplication(self):
        self.assertEqual(translate("sin(x)"), "sin(x)")

    def test_invalid_character_raises(self):
        with self.assertRaises(ExpressionError):
            compile_expression("x = 3")


class EvaluationTests(unittest.TestCase):
    def ev(self, expr, **scope):
        return evaluate_scalar(expr, scope)

    def test_simple_expression(self):
        self.assertEqual(self.ev("2 * x + 1", x=3), 7)

    def test_trig_function(self):
        self.assertEqual(self.ev("sin(0)"), 0)

    def test_precedence_and_unary_minus(self):
        self.assertEqual(self.ev("-2^2"), -4)
        self.assertEqual(self.ev("2^3^2"), 512)

    def test_constants(self):
        self.assertAlmostEqual(self.ev("pi"), math.pi)
        self.assertAlmostEqual(self.ev("e"), math.e)

    def test_domain_error_is_nan(self):
        self.assertTrue(math.isnan(self.ev("sqrt(x)", x=-1)))

    def test_fractional_power_of_negative_is_nan_not_complex(self):
        self.assertTrue(math.isnan(self.ev("(-8)^(1/3)")))

    def test_invalid_expression_is_nan(self):
        self.assertTrue(math.isnan(self.ev("not a valid expr (((", x=1)))

    def test_division_by_zero_is_nan(self):
        self.assertTrue(math.isnan(self.ev("1 / x", x=0)))

    def test_unknown_symbol_and_function_are_nan(self):
        self.assertTrue(math.isnan(self.ev("foo(x)", x=1)))
        self.assertTrue(math.isnan(self.ev("q + 1")))

    def test_never_throws_on_garbage(self):
        for expr in ["", None, "   ", "))((", "__import__('os')", "x[0]"]:
            self.assertTrue(math.isnan(evaluate_scalar(expr, {"x": 1})), expr)

    def test_grid_nan_mask_matches_domain(self):
        xs = np.linspace(-2, 2, 5)
        out = evaluate_on_grid("sqrt(x)", {"x": xs}, xs.shape)
        np.testing.assert_array_equal(np.isnan(out), xs < 0)

    def test_constant_expression_broadcasts(self):
        out = evaluate_on_grid("3", {"x": np.arange(4.0)}, (4,))
        self.assertEqual(list(out), [3.0, 3.0, 3.0, 3.0])


class PlotDataTests(unittest.TestCase):
    def test_2d_uses_800_points_and_labels(self):
        spec = {
            "kind": "2d",
            "variables": ["x"],
            "domain": {"xMin": -10, "xMax": 10},
            "traces": [{"expr": "x", "label": "identity"}, {"expr": "x^2"}],
        }
        data = compute_2d(spec)
        self.assertEqual(len(data.xs), POINTS_2D)
        self.assertEqual([c.label for c in data.curves], ["identity", "x^2"])
        self.assertAlmostEqual(data.curves[0].ys[-1], 10.0)

    def test_2d_default_domain(self):
        data = compute_2d({"traces": [{"expr": "x"}]})
        self.assertEqual(data.xs[0], -10)
        self.assertEqual(data.xs[-1], 10)

    def test_3d_grid_and_palette(self):
        spec = {
            "kind": "3d",
            "variables": ["x", "y"],
            "domain": {"xMin": -2, "xMax": 2},
            "traces": [{"expr": "x^2 + y^2"}, {"expr": "x*y"}],
        }
        data = compute_3d(spec)
        self.assertEqual(data.X.shape, (POINTS_3D, POINTS_3D))
        self.assertEqual(data.Y.shape, (POINTS_3D, POINTS_3D))
        self.assertEqual(data.surfaces[0].color, SURFACE_COLORS[0])
        self.assertEqual(data.surfaces[1].color, SURFACE_COLORS[1])
        self.assertAlmostEqual(data.surfaces[0].zs[-1, -1], 8.0)

    def test_3d_without_traces_plots_zero_surface(self):
        data = compute_3d({"kind": "3d", "variables": ["x", "y"], "traces": []})
        self.assertEqual(len(data.surfaces), 1)
        self.assertTrue(np.all(data.surfaces[0].zs == 0))


if __name__ == "__main__":
    unittest.main()
