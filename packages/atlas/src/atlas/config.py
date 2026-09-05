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

    mcp_ticketing_url: str = "http://localhost:8801/mcp"
    mcp_docstore_url: str = "http://localhost:8802/mcp"

    seed: int = 1337
    canary_seed: int = 1337

    refund_threshold_usd: float = 500.0

    outbox_dir: str = "var/outbox"


settings = Settings()
