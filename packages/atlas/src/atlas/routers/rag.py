import uuid

from atlas_retrieval import hash_text, wrap_chunk
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from atlas import ollama_client
from atlas.config import settings
from atlas.db.retrieval import RetrievedChunk, authorized_search
from atlas.decision_log import insert_decision_log, list_decisions, update_response_hash
from atlas.prompts import build_system_prompt

router = APIRouter()


class RagRequest(BaseModel):
    query: str
    session_id: str | None = None
    seed: int | None = None
    temperature: float | None = None


class RagChunk(BaseModel):
    title: str
    category: str
    owner_role: str


class RagResponse(BaseModel):
    reply: str
    retrieved: list[RagChunk]


def build_rag_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Build the user-turn prompt from retrieved chunks.

    MITIGATED (Project 2, was LLM01:2026 — Prompt Injection): each chunk is
    now wrapped in an explicit provenance/untrusted-data marker
    (atlas_retrieval.wrap_chunk), and the system prompt states plainly what
    that marker means (atlas.prompts.TRUST_BOUNDARY clause). This is
    defense in depth, not a security boundary — see
    packages/atlas-retrieval/README.md for why. See WEAKNESSES.md.
    """
    context = "\n\n".join(
        wrap_chunk(chunk.source_doc_id, "untrusted", chunk.body) for chunk in chunks
    )
    return f"{context}\n\n{question}"


@router.post("/rag/query")
async def rag_query(
    request: Request,
    body: RagRequest,
    x_atlas_role: str = Header(default="broker"),
) -> RagResponse:
    http_client = request.app.state.http_client
    pool = request.app.state.db_pool

    [embedding] = await ollama_client.embed(http_client, [body.query])
    result = await authorized_search(
        pool,
        http_client,
        settings.control_base_url,
        embedding,
        x_atlas_role,
        settings.retrieval_mode,
    )
    chunks = result.chunks

    # Decision log (Project 2 — the headline deliverable): every retrieval
    # is recorded, whether or not anything was denied, so an EU AI Act
    # Article 12 audit can answer "who saw what, and who authorized it"
    # without relying on anyone's memory of what happened.
    request_id = str(uuid.uuid4())
    log_id = await insert_decision_log(
        pool,
        request_id,
        x_atlas_role,
        body.session_id,
        hash_text(body.query),
        mode=result.mode,
        candidate_chunk_ids=result.candidate_chunk_ids,
        decisions=result.decisions,
        context_chunk_ids=[c.chunk_id for c in chunks],
        redactions_applied=[],
    )

    messages = [
        {"role": "system", "content": build_system_prompt(x_atlas_role)},
        {"role": "user", "content": build_rag_prompt(body.query, chunks)},
    ]
    reply = await ollama_client.chat(
        http_client, messages, seed=body.seed, temperature=body.temperature
    )
    reply_text = reply.get("content", "")
    await update_response_hash(pool, log_id, hash_text(reply_text))

    return RagResponse(
        reply=reply_text,
        retrieved=[
            RagChunk(title=c.title, category=c.category, owner_role=c.owner_role) for c in chunks
        ],
    )


@router.get("/retrieval/decisions")
async def retrieval_decisions(
    request: Request,
    role: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query interface for the decision log — EU AI Act Article 12
    record-keeping evidence. See packages/atlas-retrieval/README.md for a
    worked example."""
    pool = request.app.state.db_pool
    return await list_decisions(pool, role=role, since=since, until=until, limit=limit)
