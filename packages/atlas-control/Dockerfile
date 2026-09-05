# syntax=docker/dockerfile:1
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --package atlas-control --no-dev

FROM python:3.13-slim AS runtime
# atlas-control shells out to the real opa binary for policy evaluation
# (see src/atlas_control/policy.py) — pinned to the same version verified
# locally (1.19.0) so `opa test` results are reproducible between dev and
# this image.
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL -o /usr/local/bin/opa \
      "https://openpolicyagent.org/downloads/v1.19.0/opa_linux_${TARGETARCH}_static" && \
    chmod +x /usr/local/bin/opa && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 atlas
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages/atlas-control/src /app/packages/atlas-control/src
COPY --from=builder /app/packages/atlas-control/policy /app/packages/atlas-control/policy
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
ENV ATLAS_CONTROL_POLICY_DIR=/app/packages/atlas-control/policy
USER atlas
EXPOSE 8100
CMD ["uvicorn", "atlas_control.app:app", "--host", "0.0.0.0", "--port", "8100"]
