import uuid

from atlas_retrieval import ChunkLogEntry, hash_text
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from atlas import ollama_client
from atlas.db.retrieval import RetrievedChunk, search
from atlas.decision_log import insert_decision_log, update_response_hash
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

    WEAKNESS (LLM01:2026 — Prompt Injection): retrieved chunks are
    concatenated directly into the prompt with no trust delimiter and no
    provenance marker distinguishing them from the operator's instructions.
    Anything embedded in a document body is read by the model with the same
    trust level as the question itself. See WEAKNESSES.md.
    """
    context = "\n\n".join(chunk.body for chunk in chunks)
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
    chunks = await search(pool, embedding, x_atlas_role)

    # Decision log (Project 2 Phase A): logged even before any
    # authorization filter exists, so the log itself is evidence of the
    # vulnerability — every candidate is recorded as "allowed" under
    # mode="none" because that's the true state of the unmodified code.
    # This becomes the honest before-state for the worked README example.
    request_id = str(uuid.uuid4())
    decisions = [
        ChunkLogEntry(
            chunk_id=c.chunk_id,
            allowed_roles=c.allowed_roles,
            allow=True,
            rule="no_authorization_check_pre_project2",
        )
        for c in chunks
    ]
    log_id = await insert_decision_log(
        pool,
        request_id,
        x_atlas_role,
        body.session_id,
        hash_text(body.query),
        mode="none",
        candidate_chunk_ids=[c.chunk_id for c in chunks],
        decisions=decisions,
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
