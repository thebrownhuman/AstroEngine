"""The OpenAI-compatible backend (DeepSeek via the homelab gateway) must look
exactly like the Anthropic client to the /v1/ask tool loop."""
import json

import httpx
import pytest

from astro_llm import qa
from astro_llm.openai_compat import OpenAICompatClient

TOOLS = [{"name": "get_vedic_chart", "description": "chart",
          "input_schema": {"type": "object", "properties": {}}}]


def _client(replies, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=replies.pop(0))
    return OpenAICompatClient("http://gw/v1", "k", transport=httpx.MockTransport(handler))


def _reply(content=None, calls=()):
    return {"choices": [{"message": {"role": "assistant", "content": content, "tool_calls": [
        {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
        for cid, name, args in calls] or None}}]}


def test_request_translation_and_tool_use_blocks():
    seen = []
    client = _client([_reply("thinking", [("c1", "get_vedic_chart", {"include_yogas": True})])], seen)
    response = client.messages.create(
        model="deepseek-chat", max_tokens=100, system="SYS", tools=TOOLS,
        tool_choice={"type": "auto"}, messages=[{"role": "user", "content": "lagna?"}])
    body = seen[0]
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["tools"][0]["function"]["parameters"] == TOOLS[0]["input_schema"]
    assert body["tool_choice"] == "auto"
    text, use = response.content
    assert (text.type, text.text) == ("text", "thinking")
    assert (use.type, use.id, use.name, use.input) == ("tool_use", "c1", "get_vedic_chart", {"include_yogas": True})


def test_history_with_tool_results_round_trips():
    seen = []
    client = _client([_reply("ok")], seen)
    first = _reply(None, [("c1", "get_vedic_chart", {})])
    assistant = OpenAICompatClient._blocks(first["choices"][0]["message"])
    client.messages.create(
        model="m", max_tokens=10, system="S", tools=TOOLS,
        tool_choice={"type": "tool", "name": "report_answer"},
        messages=[{"role": "user", "content": "q"},
                  {"role": "assistant", "content": assistant},
                  {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{}"}]}])
    body = seen[0]
    assert body["tool_choice"] == {"type": "function", "function": {"name": "report_answer"}}
    assert body["messages"][2]["tool_calls"][0]["id"] == "c1"
    assert body["messages"][3] == {"role": "tool", "tool_call_id": "c1", "content": "{}"}


def test_bad_tool_arguments_become_empty_input():
    seen = []
    reply = {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "x", "arguments": "{not json"}}]}}]}
    response = _client([reply], seen).messages.create(
        model="m", max_tokens=1, system="", tools=[], tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": "q"}])
    assert response.content[0].input == {}


def test_deepseek_env_selects_compat_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ASTRO_LLM_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://gw/v1")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    assert isinstance(qa._client(), OpenAICompatClient)
    assert qa.model_name() == "deepseek-chat"


def test_no_backend_configured(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(qa.NotConfigured):
        qa._client()
