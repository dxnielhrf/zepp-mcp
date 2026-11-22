# syntax=docker/dockerfile:1
# Build from the repository root:  docker compose -f deploy/compose.yaml build
# Linux test run:                  docker build -f deploy/Dockerfile --target test .

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY zepp_mcp ./zepp_mcp
# Server dependencies exactly as locked; the package itself installed, not linked.
RUN uv sync --frozen --no-dev --no-editable
# shortcut: mcp-proxy is pinned by version, its own deps are not locked; add it to uv.lock if builds drift.
RUN uv pip install --python /app/.venv/bin/python mcp-proxy==0.15.0

FROM build AS test
COPY tests ./tests
COPY tools ./tools
RUN uv sync --frozen && uv run --frozen pytest

FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin zepp \
 && install -d -m 700 -o 10001 -g 10001 /data/zepp
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ZEPP_TOKEN_CACHE=/data/zepp/token.json
USER 10001
EXPOSE 8000
# stdio server behind a Streamable HTTP bridge at /mcp. The Host check stays on:
# the reverse proxy forwards with Host zepp:8000.
ENTRYPOINT ["mcp-proxy", "--host", "0.0.0.0", "--port", "8000", "--allowed-host", "zepp:8000", "--pass-environment", "--", "zepp-mcp"]
