"""Evidence paths: how a claim points into the engine output it rests on.

A path is `<result_id>.<key>.<key>...`, e.g. `t1.grahas.Moon.nakshatra` or
`t1.current_dasha.chain.0.end`. `result_id` names one tool result of the
conversation (`t1`, `t2`, ... in call order). List items are addressed by a
numeric segment; `[0]` is accepted as a spelling of `.0`.
"""

from __future__ import annotations

import re

_MISSING = object()
FLAGGED_SOURCES = ("provider_compatible", "unverified")


def split_path(path: str) -> list[str]:
    path = re.sub(r"\[(\d+)\]", r".\1", path.strip())
    return [part for part in path.split(".") if part != ""]


def resolve(results: dict[str, object], path: str):
    """The value at `path`, or `_MISSING` when any segment does not exist."""
    parts = split_path(path)
    if not parts or parts[0] not in results:
        return _MISSING
    node = results[parts[0]]
    for part in parts[1:]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return _MISSING
    return node


def exists(results: dict[str, object], path: str) -> bool:
    return resolve(results, path) is not _MISSING


def provenance_along(results: dict[str, object], path: str) -> set[str]:
    """Every `source` stamp on the way from the result root down to `path`.

    Stamps sit on the block (`source`), on a sibling (`<block>_source`) or in
    the chart's `sources` map, so all three are checked at each level.
    """
    parts = split_path(path)
    if not parts or parts[0] not in results:
        return set()
    found: set[str] = set()
    node = results[parts[0]]
    if isinstance(node, dict) and isinstance(node.get("sources"), dict) and len(parts) > 1:
        stamp = node["sources"].get(parts[1])
        if isinstance(stamp, dict) and isinstance(stamp.get("source"), str):
            found.add(stamp["source"])
    for part in parts[1:]:
        if isinstance(node, dict):
            if isinstance(node.get("source"), str):
                found.add(node["source"])
            # `balance_at_birth_years` is stamped by `balance_at_birth_source`.
            for key in {f"{part}_source", f"{part.rsplit('_', 1)[0]}_source"}:
                sibling = node.get(key)
                if isinstance(sibling, dict) and isinstance(sibling.get("source"), str):
                    found.add(sibling["source"])
            if part not in node:
                break
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            break
    if isinstance(node, dict) and isinstance(node.get("source"), str):
        found.add(node["source"])
    return found


def validate_claims(claims: list[dict], results: dict[str, object]) -> tuple[list[dict], list[dict]]:
    """Split claims into (kept, dropped).

    A kept claim has at least one evidence path, and every path it cites
    resolves. Paths that do not resolve are never silently kept: one bad path
    drops the claim, with the reason recorded.
    """
    kept, dropped = [], []
    for claim in claims or []:
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("text", "")).strip()
        evidence = [str(p) for p in (claim.get("evidence") or []) if str(p).strip()]
        if not text:
            continue
        missing = [p for p in evidence if not exists(results, p)]
        if not evidence:
            dropped.append({"text": text, "evidence": [], "reason": "no evidence cited"})
            continue
        if missing:
            dropped.append({"text": text, "evidence": evidence,
                            "reason": "evidence does not resolve", "unresolved": missing})
            continue
        sources = set().union(*(provenance_along(results, p) for p in evidence))
        kept.append({
            "text": text,
            "evidence": evidence,
            "provenance": sorted(sources),
            "flagged_provenance": sorted(sources.intersection(FLAGGED_SOURCES)),
        })
    return kept, dropped
