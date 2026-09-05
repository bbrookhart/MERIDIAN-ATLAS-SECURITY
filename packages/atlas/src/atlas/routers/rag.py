from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from atlas import ollama_client
from atlas.db.retrieval import RetrievedChunk, search
from atlas.prompts import build_system_prompt

router = APIRouter()


class RagRequest(BaseModel):
    query: str


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

    messages = [
        {"role": "system", "content": build_system_prompt(x_atlas_role)},
        {"role": "user", "content": build_rag_prompt(body.query, chunks)},
    ]
    reply = await ollama_client.chat(http_client, messages)

    return RagResponse(
        reply=reply.get("content", ""),
        retrieved=[
            RagChunk(title=c.title, category=c.category, owner_role=c.owner_role) for c in chunks
        ],
    )
