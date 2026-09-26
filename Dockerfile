# Multi-stage minimal production container for Living Language Model Beta Service
# Governance release: OSIRIS-LIVLM-BETA-0.1.0-REF

FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build tools if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
# Install pydantic wheel into virtualenv
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir pydantic>=2.0.0

# -------------------------------------------------------------
# Runtime stage
FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="Living Language Model Beta Service" \
      org.opencontainers.image.description="Governed execution service and dynamic evidence ledger" \
      org.opencontainers.image.version="0.1.0-beta.1" \
      org.opencontainers.image.vendor="OSIRIS / DNA-Lang Project" \
      org.opencontainers.image.revision="62c3492"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED="1" \
    PYTHONPATH="/app/src" \
    PORT="8080"

# Create unprivileged application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false -M -d /app appuser

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY --chown=appuser:appgroup src/ /app/src/

# Security hardening: drop root privileges
USER appuser

EXPOSE 8080

# Native healthcheck using zero-dependency python standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; opener = urllib.request.build_opener(urllib.request.ProxyHandler({})); opener.open('http://127.0.0.1:8080/healthz', timeout=3)" || exit 1

ENTRYPOINT ["python3", "-m", "osiris_governance.livlm_service"]
