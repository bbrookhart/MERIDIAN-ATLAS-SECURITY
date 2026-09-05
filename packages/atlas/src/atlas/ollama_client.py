"""Thin async client over Ollama's REST API.

Model calls default to a local Ollama instance. An optional hosted-API flag
(ATLAS_MODEL_PROVIDER=anthropic) is available for chat, but embeddings always
go through Ollama to keep the corpus pipeline self-contained. Never hardcode
a key: the Anthropic key, if used, comes only from ATLAS_ANTHROPIC_API_KEY.
"""

from typing import Any

import httpx

from atlas.config import settings

Message = dict[str, Any]
ToolSchema = dict[str, Any]


async def chat(
    client: httpx.AsyncClient,
    messages: list[Message],
    tools: list[ToolSchema] | None = None,
    seed: int | None = None,
    temperature: float | None = None,
) -> Message:
    """Send a chat request to the configured model provider.

    `seed`/`temperature` are an optional reproducibility passthrough (used by
    the red-team harness to make individual trials replayable) — omitted,
    generation is non-deterministic as before.
    """
    if settings.model_provider == "anthropic":
        return await _chat_anthropic(client, messages, tools, temperature)
    return await _chat_ollama(client, messages, tools, seed, temperature)


async def _chat_ollama(
    client: httpx.AsyncClient,
    messages: list[Message],
    tools: list[ToolSchema] | None,
    seed: int | None,
    temperature: float | None,
) -> Message:
    payload: dict[str, Any] = {
        "model": settings.ollama_chat_model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    options: dict[str, Any] = {}
    if seed is not None:
        options["seed"] = seed
    if temperature is not None:
        options["temperature"] = temperature
    if options:
        payload["options"] = options
    resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]


async def _chat_anthropic(
    client: httpx.AsyncClient,
    messages: list[Message],
    tools: list[ToolSchema] | None,
    temperature: float | None,
) -> Message:
    if not settings.anthropic_api_key:
        raise RuntimeError("ATLAS_ANTHROPIC_API_KEY is not set")
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    rest = [m for m in messages if m["role"] != "system"]
    payload: dict[str, Any] = {
        "model": settings.anthropic_model,
        "max_tokens": 1024,
        "messages": rest,
    }
    if system:
        payload["system"] = system
    if temperature is not None:
        payload["temperature"] = temperature
    if tools:
        payload["tools"] = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {}),
            }
            for t in tools
        ]
    resp = await client.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
    tool_calls = [
        {"function": {"name": b["name"], "arguments": b["input"]}}
        for b in data["content"]
        if b["type"] == "tool_use"
    ]
    message: Message = {"role": "assistant", "content": text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


async def embed(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    resp = await client.post(
        f"{settings.ollama_base_url}/api/embed",
        json={"model": settings.ollama_embed_model, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]
