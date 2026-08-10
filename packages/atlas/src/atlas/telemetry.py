"""Process-global tracer for Atlas. OTel's TracerProvider is a global
registry by design (`trace.set_tracer_provider`), so this is configured
once at import time — the same pattern `config.settings` already uses for
its own process-global singleton — rather than threaded through
`app.state` per request.
"""

from atlas_detect import configure_tracing

from atlas.config import settings

tracer = configure_tracing("atlas", settings.otlp_endpoint)
