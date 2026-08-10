from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_CONTROL_", extra="ignore")

    database_url: str = "postgresql://atlas:atlas@localhost:5432/atlas"

    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"

    mcp_ticketing_url: str = "http://localhost:8801/mcp"
    mcp_docstore_url: str = "http://localhost:8802/mcp"

    # Capability tokens: symmetric signing key. Lab-only — a production
    # deployment would use a KMS-backed key, not an env var default.
    capability_signing_key: str = "atlas-control-lab-signing-key-not-for-production"
    capability_ttl_seconds: int = 30

    # Policy: path to the compiled Rego bundle (a directory `opa eval -d`
    # can load directly).
    policy_dir: Path = Path(__file__).resolve().parents[2] / "policy"

    # Monetary values are integer cents throughout atlas-control — not just
    # financial best practice, but a workaround for a real float-comparison
    # bug in the installed OPA build. See policy/tool_authorization.rego.
    refund_threshold_cents: int = 50000
    # Session budgets (ASI08 blast-radius controls).
    max_tool_calls_per_session: int = 20
    max_refund_cents_per_session: int = 50000

    # Irreversible-action staged commit / rollback window.
    rollback_window_seconds: int = 30

    outbox_dir: str = "var/outbox"

    # Project 4: see atlas.config.Settings.otlp_endpoint for the same
    # opt-in-only rationale.
    otlp_endpoint: str | None = None


settings = Settings()
