import { test } from "node:test";
import assert from "node:assert/strict";
import { combineSpecs } from "../../src/combine.js";

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
