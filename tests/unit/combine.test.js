import { test } from "node:test";
import assert from "node:assert/strict";
import { canCombine, combineSpecs } from "../../src/combine.js";

const sine = {
  title: "Sine",
  kind: "2d",
  variables: ["x"],
  domain: { xMin: -10, xMax: 10 },
  traces: [{ expr: "sin(x)", label: "sin" }],
};

const cosine = {
  title: "Cosine",
  kind: "2d",
  variables: ["x"],
  domain: { xMin: -5, xMax: 5 },
  traces: [{ expr: "cos(x)", label: "cos" }, { expr: "x", label: "extra" }],
};

test("combineSpecs appends only the first trace of the incoming spec", () => {
  const combined = combineSpecs(sine, cosine);
  assert.deepEqual(combined.traces, [
    { expr: "sin(x)", label: "sin" },
    { expr: "cos(x)", label: "cos" },
  ]);
});

test("combineSpecs sets the combined flag", () => {
  assert.equal(combineSpecs(sine, cosine).combined, true);
});

test("combineSpecs does not mutate the current spec", () => {
  const before = structuredClone(sine);
  combineSpecs(sine, cosine);
  assert.deepEqual(sine, before);
});

test("combineSpecs keeps the current domain and variables", () => {
  const combined = combineSpecs(sine, cosine);
  assert.deepEqual(combined.domain, sine.domain);
  assert.deepEqual(combined.variables, sine.variables);
});

test("combineSpecs joins differing titles", () => {
  assert.equal(combineSpecs(sine, cosine).title, "Sine + Cosine");
});

test("combineSpecs keeps a single title when both are equal", () => {
  assert.equal(combineSpecs(sine, { ...cosine, title: "Sine" }).title, "Sine");
});

test("combineSpecs returns current unchanged when incoming has no trace", () => {
  assert.equal(combineSpecs(sine, { title: "Empty", traces: [] }), sine);
  assert.equal(combineSpecs(sine, {}), sine);
});

test("combining a combined spec keeps accumulating traces", () => {
  const once = combineSpecs(sine, cosine);
  const twice = combineSpecs(once, { title: "Tan", traces: [{ expr: "tan(x)" }] });
  assert.equal(twice.traces.length, 3);
  assert.equal(twice.title, "Sine + Cosine + Tan");
  assert.equal(twice.combined, true);
});

const surface = {
  title: "Paraboloid",
  kind: "3d",
  variables: ["x", "y"],
  domain: { xMin: -2, xMax: 2 },
  traces: [{ expr: "x^2 + y^2", label: "paraboloid" }],
};

const saddle = {
  title: "Saddle",
  kind: "3d",
  variables: ["x", "y"],
  domain: { xMin: -1, xMax: 1 },
  traces: [{ expr: "x^2 - y^2", label: "saddle" }],
};

test("canCombine allows 2D into 2D", () => {
  assert.equal(canCombine(sine, cosine), true);
});

test("canCombine allows 3D into 3D", () => {
  assert.equal(canCombine(surface, saddle), true);
});

test("canCombine rejects 2D into 3D", () => {
  assert.equal(canCombine(surface, cosine), false);
});

test("canCombine rejects 3D into 2D", () => {
  assert.equal(canCombine(sine, saddle), false);
});

test("canCombine treats a missing kind as 2D", () => {
  assert.equal(canCombine({ traces: [] }, sine), true);
  assert.equal(canCombine(surface, { traces: [] }), false);
});

test("combineSpecs keeps kind 3d when combining 3D specs", () => {
  const combined = combineSpecs(surface, saddle);
  assert.equal(combined.kind, "3d");
  assert.equal(combined.combined, true);
});

test("combineSpecs appends the 3D trace to the current traces", () => {
  const combined = combineSpecs(surface, saddle);
  assert.deepEqual(combined.traces, [
    { expr: "x^2 + y^2", label: "paraboloid" },
    { expr: "x^2 - y^2", label: "saddle" },
  ]);
  assert.deepEqual(combined.variables, ["x", "y"]);
  assert.deepEqual(combined.domain, surface.domain);
});
