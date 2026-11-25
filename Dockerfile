FROM python:3.14-slim AS base

ENV MALLOC_ARENA_MAX=2 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_CERTS=true \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_PREFERENCE=only-system

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends tzdata && \
    groupadd -g 8508 dBot && \
    useradd -u 8508 -g 8508 dBot -m

WORKDIR /opt/app

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

FROM base AS runner

COPY --from=builder /opt/venv /opt/venv

COPY --chown=dBot:dBot . .

USER dBot

CMD ["python", "dBot.py"]
