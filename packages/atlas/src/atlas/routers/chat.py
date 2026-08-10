from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from atlas import ollama_client
from atlas.prompts import build_system_prompt

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    seed: int | None = None
    temperature: float | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    x_atlas_role: str = Header(default="broker"),
) -> ChatResponse:
    """LLM-as-component customer-service chat. Stateless: no memory, no tools."""
    http_client = request.app.state.http_client
    messages = [
        {"role": "system", "content": build_system_prompt(x_atlas_role)},
        {"role": "user", "content": body.message},
    ]
    reply = await ollama_client.chat(
        http_client, messages, seed=body.seed, temperature=body.temperature
    )
    return ChatResponse(reply=reply.get("content", ""))
