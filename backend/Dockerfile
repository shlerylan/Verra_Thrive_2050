FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home thrive && mkdir /uploads && chown thrive /uploads
COPY alembic.ini ./
COPY alembic ./alembic
USER thrive
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
