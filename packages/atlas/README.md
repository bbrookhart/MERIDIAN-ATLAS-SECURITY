# Atlas

**This is an intentionally vulnerable lab target.** Atlas simulates Meridian
Mutual's internal AI assistant. It runs on `127.0.0.1` only, holds
exclusively synthetic (Faker-generated) data, and is never deployed. Every
weakness listed in [`WEAKNESSES.md`](./WEAKNESSES.md) was built in on
purpose — do not fix them; they are the point.

## What is this

Atlas is Project 0 of a six-project AI security portfolio
(`meridian-atlas-security`). It is the shared target that every other
project attacks, hardens, observes, or scores. It's deliberately small —
readable end to end in about ten minutes.

## Architecture

```
                          host machine
                     ┌──────────────────┐
                     │  Ollama (11434)  │
                     │  llama3.2,       │
                     │  nomic-embed-text│
                     └────────▲─────────┘
                              │ host.docker.internal
   ┌──────────────────────────┼─────────────────────────┐
   │ docker compose            │           atlas_egress   │
   │                    ┌──────┴──────┐                   │
   │   127.0.0.1:8000 → │  atlas-api  │                   │
   │                    │  (FastAPI)  │                   │
   │                    └──┬───┬───┬──┘                   │
   │           atlas_internal │   │                        │
   │        ┌───────────┘    │   └───────────┐            │
   │  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐    │
   │  │  postgres   │  │mcp-ticketing│  │ mcp-docstore│    │
   │  │  +pgvector  │  │ (streamable-│  │ (streamable-│    │
   │  │             │  │    http)    │  │    http)    │    │
   │  └─────────────┘  └─────────────┘  └─────────────┘    │
   └─────────────────────────────────────────────────────┘
```

Four surfaces: `/chat` (LLM as component), `/rag/query` (retrieval over a
synthetic corpus), `/agent/act` (a tool-using agent), and two real MCP
servers (a mock ticketing system, a mock document store) the agent connects
to as a client.

## Prerequisites

- `ollama serve` running on the host, with two models pulled once:
  ```
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```
- Docker + Docker Compose.

## Quickstart

```
export GIT_SHA=$(git rev-parse HEAD)
docker compose -f packages/atlas/docker-compose.yml up --build
curl http://127.0.0.1:8000/version
```

## Surfaces

```
curl -X POST http://127.0.0.1:8000/chat \
  -H 'X-Atlas-Role: broker' -H 'Content-Type: application/json' \
  -d '{"message": "What is my policy coverage?"}'

curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'X-Atlas-Role: broker' -H 'Content-Type: application/json' \
  -d '{"query": "salary band review notes"}'

curl -X POST http://127.0.0.1:8000/agent/act \
  -H 'X-Atlas-Role: adjuster' -H 'Content-Type: application/json' \
  -d '{"session_id": "demo", "message": "Look up claim CLM-00001"}'
```

The MCP servers speak the streamable-HTTP MCP transport directly at
`http://localhost:8801/mcp` (ticketing) and `http://localhost:8802/mcp`
(docstore) — connect with the `mcp` Python SDK client or an MCP inspector.

## Roles

`X-Atlas-Role: broker | adjuster | hr` selects which system-prompt framing
and (nominally) which document set a caller should see. It is **not**
enforced at retrieval time — see weakness #1 in `WEAKNESSES.md`.

## Configuration

See [`env.example`](./env.example) for the full list of environment
variables (Ollama URLs/models, database URL, MCP server URLs, refund
threshold, seeds). Copy to `.env` for local, non-Docker runs.

## Seeding

`docker compose` runs a one-shot `seed` service that populates ~200
synthetic documents deterministically from a fixed seed. To reseed by hand:

```
uv run --package atlas atlas-seed
```

## Running tests

```
uv run --package atlas pytest
```

## Security notes

- In-container `uvicorn` binds `0.0.0.0` (required for compose networking —
  a container's own loopback isn't reachable from other containers or from
  published ports). The "127.0.0.1 only" guarantee is enforced by the
  compose `ports:` mapping (`127.0.0.1:8000:8000`), not the bind address.
  The non-Docker entrypoint (`src/atlas/main.py`) binds literally
  `127.0.0.1`.
- `postgres`, `mcp-ticketing`, and `mcp-docstore` sit on a docker-compose
  network with `internal: true` — zero route out, structurally enforced.
  `atlas-api` additionally joins an egress network solely to reach the
  host's Ollama. The "only calls the model endpoint" guarantee is therefore
  a combined code + network control: nothing in this codebase calls any host
  except `ATLAS_OLLAMA_BASE_URL`, backed structurally by the DB/MCP tier
  having no egress regardless.
- See [`WEAKNESSES.md`](./WEAKNESSES.md) for the full list of deliberate
  weaknesses and their OWASP 2026 IDs.

## Repo layout

```
src/atlas/
├── app.py, main.py, config.py, prompts.py, canaries.py, credentials.py
├── ollama_client.py, mcp_client.py, memory.py, cli.py, seed.py
├── routers/     # /version, /chat, /rag/query, /agent/act
├── db/          # asyncpg pool, schema, retrieval
├── tools/       # lookup_claim, issue_refund, send_email, search_kb
└── mcp_servers/ # ticketing, docstore (real MCP servers)
```
