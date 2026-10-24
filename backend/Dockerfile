FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --locked --no-dev --no-editable && useradd --uid 10001 --create-home thrive && mkdir /uploads && chown thrive /uploads
COPY alembic.ini ./
COPY alembic ./alembic
USER thrive
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
