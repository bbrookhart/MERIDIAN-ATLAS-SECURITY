"""Process-global tracer for atlas-control. Same rationale as
atlas.telemetry — see that module's docstring.
"""

from atlas_detect import configure_tracing

from atlas_control.config import settings

tracer = configure_tracing("atlas-control", settings.otlp_endpoint)
