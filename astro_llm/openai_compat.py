"""OpenAI-compatible chat backend (DeepSeek through the homelab gateway).

Exposes the slice of the Anthropic client that `qa.ask` uses —
`client.messages.create(...)` returning `.content` blocks of type "text" and
"tool_use" — so the tool loop does not care which provider is behind it.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

TIMEOUT = 120.0


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, transport=None):
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=TIMEOUT, transport=transport,
            headers={"Authorization": f"Bearer {api_key}"})
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, *, model, max_tokens, system, tools, tool_choice, messages):
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}]
                        + [m for msg in messages for m in self._to_openai(msg)],
            "tools": [{"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""),
                "parameters": t["input_schema"]}} for t in tools],
            "tool_choice": ({"type": "function", "function": {"name": tool_choice["name"]}}
                            if tool_choice.get("type") == "tool" else "auto"),
        }
        response = self._http.post("/chat/completions", json=body)
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        return SimpleNamespace(content=self._blocks(message))

    @staticmethod
    def _to_openai(msg: dict) -> list[dict]:
        content = msg["content"]
        if isinstance(content, str):
            return [{"role": msg["role"], "content": content}]
        if msg["role"] == "user":
            # A list on the user side is always tool results.
            return [{"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]}
                    for b in content]
        text = "".join(b.text for b in content if b.type == "text")
        calls = [{"id": b.id, "type": "function", "function": {
            "name": b.name, "arguments": json.dumps(b.input or {})}}
            for b in content if b.type == "tool_use"]
        out = {"role": "assistant", "content": text or None}
        if calls:
            out["tool_calls"] = calls
        return [out]

    @staticmethod
    def _blocks(message: dict) -> list:
        blocks = []
        if message.get("content"):
            blocks.append(SimpleNamespace(type="text", text=message["content"]))
        for call in message.get("tool_calls") or []:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            blocks.append(SimpleNamespace(type="tool_use", id=call["id"],
                                          name=call["function"]["name"],
                                          input=args if isinstance(args, dict) else {}))
        return blocks
