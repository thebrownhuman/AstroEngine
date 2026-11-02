"""Compact fact sheet from the engine's /v1/chart, /v1/rules and /v1/shadbala."""

from __future__ import annotations

MAX_RULES = 40


def _date(iso: str | None) -> str:
    return (iso or "")[:10]


def placements(chart: dict) -> dict[str, dict]:
    return {name: {"sign": g["sign"], "sign_en": g["sign_en"], "house": g["house"]}
            for name, g in chart["grahas"].items()}


def fact_sheet(chart: dict, rules: dict, shadbala: dict) -> str:
    out: list[str] = []
    lg = chart["lagna"]
    out.append(f"Lagna: {lg['sign']} ({lg['sign_en']}) {lg['dms']}, "
               f"{lg['nakshatra']} pada {lg['nakshatra_pada']}")

    out.append("\nGrahas:")
    for name, g in chart["grahas"].items():
        d = g.get("dignity") or {}
        flags = [d.get("state") or "?"]
        if g.get("retrograde"):
            flags.append("retrograde")
        if d.get("combust"):
            flags.append("combust")
        out.append(f"- {name}: {g['sign']} ({g['sign_en']}), house {g['house']}, "
                   f"{g['dms']}, {g['nakshatra']} pada {g['nakshatra_pada']}; "
                   + ", ".join(flags))

    out.append("\nHouses:")
    for h in chart["houses"]:
        occ = ", ".join(h.get("occupants") or []) or "empty"
        out.append(f"- House {h['house']} ({h['sign']['name']}): lord {h['lord']}; {occ}")

    cur = chart.get("current_dasha") or {}
    if cur.get("chain"):
        out.append(f"\nCurrent Vimshottari dasha (as of {_date(cur.get('as_of'))}):")
        for p in cur["chain"]:
            out.append(f"- {p['level']} {p['lord']}: {_date(p['start'])} to {_date(p['end'])}")

    yogas = [y for grp in (chart.get("yogas") or {}).get("yoga_details", [])
             for y in grp.get("yoga_list", []) if y.get("has_yoga")]
    out.append("\nYogas present:" if yogas else "\nYogas present: none")
    for y in yogas:
        out.append(f"- {y['name']}: {y.get('reason', '')}")

    planets = shadbala.get("planets") or {}
    if planets:
        out.append("\nShadbala (rupas, strong?, rank):")
        for name, p in planets.items():
            out.append(f"- {name}: {p['total_rupas']} rupas, "
                       f"{'strong' if p['is_strong'] else 'weak'}, rank {p['rank']}")

    fired = rules.get("rules") or []
    out.append(f"\nClassical rules that fire ({len(fired)}):")
    for r in fired[:MAX_RULES]:
        src = r.get("source") or {}
        out.append(f"- [{r['id']}] {r['meaning']} ({src.get('book', '')} "
                   f"{src.get('edition', '')} ch.{src.get('ch')} v.{src.get('v')})")
    return "\n".join(out)


def summary(chart: dict) -> str:
    lg = chart["lagna"]
    moon = chart["grahas"]["Moon"]
    chain = (chart.get("current_dasha") or {}).get("chain") or []
    dasha = "/".join(p["lord"] for p in chain)
    return (f"{lg['sign']} lagna, Moon in {moon['sign']} ({moon['nakshatra']})"
            + (f", running {dasha} dasha" if dasha else ""))
