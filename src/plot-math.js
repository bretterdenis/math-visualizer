// Pure, dependency-free(ish) math helpers used by the plotting UI.
//
// These are extracted from main.js so they can be unit-tested from Node
// without needing a DOM or Tauri's `invoke` bridge. The browser still gets
// mathjs as a global `math` object via the CDN <script> tag in index.html;
// `safeEval` defaults to that global but accepts an injected evaluator so
// tests can supply their own (e.g. a real mathjs instance imported via npm).

/**
 * Returns `n` evenly spaced numbers from `min` to `max` (inclusive of both
 * endpoints when n > 1).
 */
export function linspace(min, max, n) {
  const out = new Array(n);
  if (n === 1) {
    out[0] = min;
    return out;
  }
  const step = (max - min) / (n - 1);
  for (let i = 0; i < n; i++) out[i] = min + step * i;
  return out;
}

function defaultEvaluator(expr, scope) {
  return globalThis.math.evaluate(expr, scope);
}

/**
 * Evaluates `expr` with the given `scope`, returning NaN instead of
 * throwing for invalid expressions, domain errors (e.g. sqrt(-1)), or any
 * non-finite/non-numeric result (e.g. complex numbers, Infinity).
 *
 * `evaluator` defaults to `globalThis.math.evaluate` (mathjs, loaded as a
 * global in the browser); tests can pass their own.
 */
export function safeEval(expr, scope, evaluator = defaultEvaluator) {
  try {
    const v = evaluator(expr, scope);
    return typeof v === "number" && Number.isFinite(v) ? v : NaN;
  } catch {
    return NaN;
  }
}
