from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", extra="ignore")

    build_sha: str = "dev"

    database_url: str = "postgresql://atlas:atlas@localhost:5432/atlas"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    embed_dimensions: int = 768

    model_provider: str = "ollama"  # "ollama" | "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # atlas-control: the agent has no DB connection or MCP client of its
    # own for tool execution anymore (Project 3) — every tool invocation,
    # native or MCP, goes through this service.
    control_base_url: str = "http://localhost:8100"

    seed: int = 1337
    canary_seed: int = 1337

    # Project 2: pre-filter resolves the caller's permitted allowed_roles
    # set before the vector query runs; post-filter runs an unfiltered
    # query and discards unauthorized candidates after. Both are real,
    # both go through atlas-control's OPA policy — this flag only picks
    # which SQL runs and when the authorization check happens. Default is
    # "pre"; see packages/atlas-retrieval/README.md for the measured
    # latency/recall tradeoff behind that default.
    retrieval_mode: str = "pre"  # "pre" | "post"

    # Informational only — the enforced value lives in
    # atlas-control/policy/tool_authorization.rego as integer cents. Kept
    # here so the system prompt can state an accurate figure; changing this
    # without also changing the policy changes nothing about what's
    # actually allowed.
    refund_threshold_usd: float = 500.0


settings = Settings()
