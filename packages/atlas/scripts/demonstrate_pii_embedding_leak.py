"""One-off live demonstration of why PII must be redacted *before*
embedding, never after. Run against a live Ollama:

    uv run --package atlas python packages/atlas/scripts/demonstrate_pii_embedding_leak.py

Simulates the wrong order: embed the raw text (containing a synthetic
SSN), redact the *text* afterward, but keep the embedding that was already
computed from the raw value — the bug this project's real order (seed.py's
_redact_all() runs before _embed_all()) avoids. Then shows that a fresh
query embedding of the raw SSN value still ranks the stale "redacted"
record's embedding highly: the vector encodes what the text no longer
shows.
"""

import asyncio
import math

import httpx
from atlas import ollama_client
from atlas_retrieval import redact_pii

RAW_TEXT = "Employee ID: EMP-99999. SSN: 078-05-1120. Salary band: B2."


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


async def main() -> None:
    async with httpx.AsyncClient() as http_client:
        # The bug this project avoids: embed first, redact the text after.
        [stale_embedding] = await ollama_client.embed(http_client, [RAW_TEXT])
        redacted_text, applied = redact_pii(RAW_TEXT)
        print(f"Raw text:      {RAW_TEXT!r}")
        print(f"Redacted text: {redacted_text!r} (redacted: {applied})")
        print("Embedding was computed BEFORE redaction (the wrong order) and kept as-is.")

        # An attacker who only sees `redacted_text` in a UI still has this
        # embedding available for semantic search (it's what's actually
        # stored/searched) — probe it with the raw SSN value, and compare
        # against a decoy SSN that never appeared anywhere in the text, to
        # establish what "no real signal" looks like on this same scale.
        [ssn_query_embedding] = await ollama_client.embed(http_client, ["SSN: 078-05-1120"])
        [decoy_query_embedding] = await ollama_client.embed(http_client, ["SSN: 999-99-9999"])
        [redacted_query_embedding] = await ollama_client.embed(http_client, [redacted_text])

        sim_to_raw_ssn = _cosine(stale_embedding, ssn_query_embedding)
        sim_to_decoy_ssn = _cosine(stale_embedding, decoy_query_embedding)
        sim_to_redacted_text = _cosine(stale_embedding, redacted_query_embedding)

        print(
            f"cosine(stale_embedding, embed('078-05-1120'))  [the real SSN]  = {sim_to_raw_ssn:.4f}"
        )
        print(
            f"cosine(stale_embedding, embed('999-99-9999'))  [decoy SSN]     = {sim_to_decoy_ssn:.4f}"
        )
        print(
            f"cosine(stale_embedding, embed(redacted_text))                  = {sim_to_redacted_text:.4f}"
        )
        print(
            f"The real SSN scores {sim_to_raw_ssn - sim_to_decoy_ssn:+.4f} above a decoy SSN "
            "that never appeared in the text — that gap is the signal the stale (redact-after) "
            "embedding still carries, even though the stored TEXT no longer shows it. "
            "Redacting text after embedding is cosmetic, not a real fix."
        )


if __name__ == "__main__":
    asyncio.run(main())
