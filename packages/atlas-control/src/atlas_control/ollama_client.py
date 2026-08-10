"""Minimal Ollama client — atlas-control needs embeddings (for search_kb)
and a small chat call (only for the approval.py naive-vs-hardened judge
demo; the agent's own planning/response generation stays in Atlas).
"""

from __future__ import annotations

import httpx

from atlas_control.config import settings

DEFAULT_CHAT_MODEL = "llama3.2"


async def embed(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    resp = await client.post(
        f"{settings.ollama_base_url}/api/embed",
        json={"model": settings.ollama_embed_model, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


async def chat(client: httpx.AsyncClient, prompt: str, model: str = DEFAULT_CHAT_MODEL) -> str:
    resp = await client.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
