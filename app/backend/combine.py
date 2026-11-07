"""Rules for overlaying a second function onto the current plot. Pure Python, no Qt."""

from __future__ import annotations

from typing import Optional


def _kind_of(spec: Optional[dict]) -> str:
    return "3d" if (spec or {}).get("kind") == "3d" else "2d"


def can_combine(current: Optional[dict], incoming: Optional[dict]) -> bool:
    """True when both specs are 2D or both are 3D. A missing kind counts as 2D."""
    return _kind_of(current) == _kind_of(incoming)


def combine_specs(current: dict, incoming: Optional[dict]) -> dict:
    """Returns a new spec with the first trace of ``incoming`` appended, marked combined.

    Titles are joined with " + " when they differ. If ``incoming`` has no trace, ``current``
    itself is returned (identity), which callers use to detect "nothing to add".
    """
    traces = (incoming or {}).get("traces") or []
    if not traces:
        return current
    trace = traces[0]

    titles: list[str] = []
    for title in (current.get("title"), (incoming or {}).get("title")):
        if title and title not in titles:
            titles.append(title)

    combined = dict(current)
    combined["title"] = " + ".join(titles)
    combined["traces"] = list(current.get("traces") or []) + [trace]
    combined["combined"] = True
    return combined
