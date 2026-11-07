"""Combine rules (port of the former tests/unit/combine.test.js)."""

import copy
import unittest

from app.backend.combine import can_combine, combine_specs

SINE = {
    "title": "Sine",
    "kind": "2d",
    "variables": ["x"],
    "domain": {"xMin": -10, "xMax": 10},
    "traces": [{"expr": "sin(x)", "label": "sin"}],
}

COSINE = {
    "title": "Cosine",
    "kind": "2d",
    "variables": ["x"],
    "domain": {"xMin": -5, "xMax": 5},
    "traces": [{"expr": "cos(x)", "label": "cos"}, {"expr": "x", "label": "extra"}],
}

SURFACE = {
    "title": "Paraboloid",
    "kind": "3d",
    "variables": ["x", "y"],
    "domain": {"xMin": -2, "xMax": 2},
    "traces": [{"expr": "x^2 + y^2", "label": "paraboloid"}],
}

SADDLE = {
    "title": "Saddle",
    "kind": "3d",
    "variables": ["x", "y"],
    "domain": {"xMin": -1, "xMax": 1},
    "traces": [{"expr": "x^2 - y^2", "label": "saddle"}],
}


class CombineSpecsTests(unittest.TestCase):
    def test_appends_only_first_trace_of_incoming(self):
        combined = combine_specs(SINE, COSINE)
        self.assertEqual(
            combined["traces"],
            [{"expr": "sin(x)", "label": "sin"}, {"expr": "cos(x)", "label": "cos"}],
        )

    def test_sets_combined_flag(self):
        self.assertTrue(combine_specs(SINE, COSINE)["combined"])

    def test_does_not_mutate_current(self):
        before = copy.deepcopy(SINE)
        combine_specs(SINE, COSINE)
        self.assertEqual(SINE, before)

    def test_keeps_current_domain_and_variables(self):
        combined = combine_specs(SINE, COSINE)
        self.assertEqual(combined["domain"], SINE["domain"])
        self.assertEqual(combined["variables"], SINE["variables"])

    def test_joins_differing_titles(self):
        self.assertEqual(combine_specs(SINE, COSINE)["title"], "Sine + Cosine")

    def test_keeps_single_title_when_equal(self):
        self.assertEqual(combine_specs(SINE, {**COSINE, "title": "Sine"})["title"], "Sine")

    def test_returns_current_unchanged_when_incoming_has_no_trace(self):
        self.assertIs(combine_specs(SINE, {"title": "Empty", "traces": []}), SINE)
        self.assertIs(combine_specs(SINE, {}), SINE)

    def test_accumulates_when_combining_a_combined_spec(self):
        once = combine_specs(SINE, COSINE)
        twice = combine_specs(once, {"title": "Tan", "traces": [{"expr": "tan(x)"}]})
        self.assertEqual(len(twice["traces"]), 3)
        self.assertEqual(twice["title"], "Sine + Cosine + Tan")
        self.assertTrue(twice["combined"])

    def test_3d_keeps_kind_and_flags_combined(self):
        combined = combine_specs(SURFACE, SADDLE)
        self.assertEqual(combined["kind"], "3d")
        self.assertTrue(combined["combined"])

    def test_3d_appends_trace_and_keeps_variables_and_domain(self):
        combined = combine_specs(SURFACE, SADDLE)
        self.assertEqual(
            combined["traces"],
            [{"expr": "x^2 + y^2", "label": "paraboloid"}, {"expr": "x^2 - y^2", "label": "saddle"}],
        )
        self.assertEqual(combined["variables"], ["x", "y"])
        self.assertEqual(combined["domain"], SURFACE["domain"])


class CanCombineTests(unittest.TestCase):
    def test_2d_into_2d(self):
        self.assertTrue(can_combine(SINE, COSINE))

    def test_3d_into_3d(self):
        self.assertTrue(can_combine(SURFACE, SADDLE))

    def test_2d_into_3d_rejected(self):
        self.assertFalse(can_combine(SURFACE, COSINE))

    def test_3d_into_2d_rejected(self):
        self.assertFalse(can_combine(SINE, SADDLE))

    def test_missing_kind_counts_as_2d(self):
        self.assertTrue(can_combine({"traces": []}, SINE))
        self.assertFalse(can_combine(SURFACE, {"traces": []}))


if __name__ == "__main__":
    unittest.main()
