FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_PROGRESS=1

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --uid 10001 app

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

USER app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "python_ai_service.bootstrap.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
