// Pure helper for overlaying a second function onto the current plot.
// Kept free of DOM and Tauri access so it can be unit-tested from Node.

/**
 * Returns a new spec with the first trace of `incoming` appended to the
 * traces of `current`, marked as combined. Titles are joined with " + " when
 * they differ. If `incoming` has no trace, `current` is returned unchanged.
 */
export function combineSpecs(current, incoming) {
  const [trace] = incoming?.traces || [];
  if (!trace) return current;

  const titles = [...new Set([current.title, incoming.title].filter(Boolean))];
  return {
    ...current,
    title: titles.join(" + "),
    traces: [...(current.traces || []), trace],
    combined: true,
  };
}
