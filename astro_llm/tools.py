"""The engine as in-process tools, plus the `report_answer` tool.

The tool schemas are the ones `/v1/tool-definitions` publishes, so the HTTP
client in examples/claude_client.py and this layer see the same contract. The
calls go straight to the endpoint functions, not over HTTP.
"""

from __future__ import annotations

import copy

from fastapi import HTTPException
from pydantic import ValidationError

from astro_engine import api

# Fields of the asker's own birth. The model may choose what to include, never
# whose chart it is: these always come from the /v1/ask request.
BIRTH_FIELDS = (
    "date", "time", "place", "latitude", "longitude", "timezone", "ayanamsa",
    "node_type", "prokerala_compatible", "strict_bphs", "reference_time",
)
OWN_CHART_TOOLS = ("get_vedic_chart", "get_kp_chart")

REPORT_ANSWER = {
    "name": "report_answer",
    "description": (
        "Submit the final answer. Call this exactly once, last. Every factual "
        "statement in `answer` must also appear as a claim with evidence paths "
        "into the tool results (`t1.grahas.Moon.nakshatra`, "
        "`t1.current_dasha.chain.0.end`). Claims whose paths do not resolve "
        "are dropped."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "Plain-language answer for the user."},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dotted paths: result id, then keys; list indices as numbers.",
                        },
                    },
                    "required": ["text", "evidence"],
                },
            },
            "refused": {
                "type": "boolean",
                "description": (
                    "True when the question asks for a prediction or "
                    "interpretation that the loaded rules cannot support."
                ),
            },
        },
        "required": ["answer", "claims", "refused"],
    },
}


def _strip_combinators(schema: dict) -> dict:
    """The Messages API rejects oneOf/anyOf/allOf at the top of input_schema."""
    schema = copy.deepcopy(schema)
    for key in ("oneOf", "anyOf", "allOf"):
        schema.pop(key, None)
    return schema


def engine_tools() -> list[dict]:
    tools = []
    for tool in api.tool_definitions():
        tool = copy.deepcopy(tool)
        tool["input_schema"] = _strip_combinators(tool["input_schema"])
        if tool["name"] in OWN_CHART_TOOLS:
            tool["description"] += (
                " The asker's birth data is filled in for you; any birth "
                "fields you pass are replaced."
            )
        tools.append(tool)
    return tools


def all_tools() -> list[dict]:
    return engine_tools() + [REPORT_ANSWER]


def _with_birth(arguments: dict, birth: dict) -> dict:
    merged = {k: v for k, v in (arguments or {}).items() if k not in BIRTH_FIELDS}
    merged.update({k: v for k, v in birth.items() if k in BIRTH_FIELDS and v is not None})
    return merged


def call_engine(name: str, arguments: dict, birth: dict) -> dict:
    """Run one engine tool. Errors come back as {"error": ...} for the model."""
    try:
        if name == "get_vedic_chart":
            return api.chart(api.ChartRequest(**_with_birth(arguments, birth)))
        if name == "get_kp_chart":
            return api.kp_report(api.ChartRequest(**_with_birth(arguments, birth)))
        if name == "get_kundli_matching":
            return api.matching_report(api.MatchRequest(**(arguments or {})))
        if name == "get_muhurta":
            return api.muhurta_report(api.DayRequest(**(arguments or {})))
    except ValidationError as exc:
        return {"error": exc.errors(include_url=False, include_context=False)}
    except HTTPException as exc:
        return {"error": exc.detail}
    except ValueError as exc:
        return {"error": str(exc)}
    return {"error": f"unknown tool {name}"}
