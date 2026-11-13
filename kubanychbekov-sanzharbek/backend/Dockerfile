FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
# retry: a dropped connection while downloading packages must not break `make up`
RUN for attempt in 1 2 3; do uv sync --frozen --no-dev --no-install-project && exit 0; echo "uv sync failed (attempt $attempt), retrying"; sleep 5; done; exit 1

COPY . .

EXPOSE 8000
# Migrations run first; compose waits for the db healthcheck instead of sleeping.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
