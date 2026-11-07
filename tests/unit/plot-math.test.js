import { test } from "node:test";
import assert from "node:assert/strict";
import { create, all } from "mathjs";
import { linspace, safeEval } from "../../src/plot-math.js";

// Real mathjs instance, standing in for the global `math` object the
// browser gets from the CDN <script> tag in index.html.
const math = create(all);
const evaluate = (expr, scope) => math.evaluate(expr, scope);

test("linspace: endpoints are exact", () => {
  const xs = linspace(-10, 10, 5);
  assert.equal(xs[0], -10);
  assert.equal(xs[xs.length - 1], 10);
});

test("linspace: returns the requested number of points", () => {
  const xs = linspace(0, 1, 11);
  assert.equal(xs.length, 11);
});

test("linspace: points are evenly spaced", () => {
  const xs = linspace(0, 10, 6);
  for (let i = 1; i < xs.length; i++) {
    assert.ok(Math.abs(xs[i] - xs[i - 1] - 2) < 1e-9);
  }
});

test("linspace: single point returns min", () => {
  const xs = linspace(3, 7, 1);
  assert.deepEqual(xs, [3]);
});

test("safeEval: evaluates a simple expression", () => {
  assert.equal(safeEval("2 * x + 1", { x: 3 }, evaluate), 7);
});

test("safeEval: evaluates trig/exp functions", () => {
  const v = safeEval("sin(0)", {}, evaluate);
  assert.equal(v, 0);
});

test("safeEval: returns NaN for a domain error (sqrt of negative)", () => {
  const v = safeEval("sqrt(x)", { x: -1 }, evaluate);
  assert.ok(Number.isNaN(v));
});

test("safeEval: returns NaN for an invalid/unparseable expression", () => {
  const v = safeEval("not a valid expr (((", { x: 1 }, evaluate);
  assert.ok(Number.isNaN(v));
});

test("safeEval: returns NaN for division by zero (Infinity is non-finite)", () => {
  const v = safeEval("1 / x", { x: 0 }, evaluate);
  assert.ok(Number.isNaN(v));
});

test("safeEval: never throws even on garbage input", () => {
  assert.doesNotThrow(() => safeEval("", {}, evaluate));
  assert.doesNotThrow(() => safeEval(undefined, {}, evaluate));
});
