# Thrive 2050

A local review foundation for storing carbon-project Excel workbooks and inspecting their metadata. This scaffold is intended for John to review before the project grows. It does **not** implement Leakage, Biomass, Matching, ExPost, ExAnte, carbon accounting, formula evaluation, or methodology validation.

Existing `code/`, `data/`, and reference-document folders were preserved. The application lives at the repository root; existing workbook and reference folders are excluded from version control. No existing workbook is automatically imported.

## Stack and requirements

- React 19 and TypeScript: reusable upload and metadata interfaces with explicit data contracts.
- Vite 8: a small development server with an API proxy and a production build. Node **22.12+ recommended** (Node 20.19+ is also compatible with the selected toolchain). npm 10+; `frontend/package-lock.json` records exact dependencies.
- Python **3.12–3.14**, with **3.13 recommended**; FastAPI provides HTTP validation and OpenAPI documentation.
- SQLAlchemy 2 and psycopg 3: explicit PostgreSQL persistence. Alembic owns schema changes; startup does not call `create_all`.
- PostgreSQL **17** and Docker Compose v2 for local infrastructure. Python dependencies and compatible ranges are defined in `backend/pyproject.toml`.

Vite's [runtime requirements](https://vite.dev/guide/) and FastAPI's [release history](https://fastapi.tiangolo.com/release-notes/) were checked when scaffolding. Docker is the simplest route when native runtimes are missing.

## Start with Docker

From this directory in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open **http://localhost:5173**. Interactive API docs: **http://localhost:8000/docs**; OpenAPI: `/openapi.json`. The backend runs `alembic upgrade head` before serving; the frontend waits for database readiness. All published ports bind to `127.0.0.1`.

`docker compose down` stops the services and preserves the named `postgres_data` and `uploaded_files` volumes. Do not remove those volumes unless their contents are no longer needed. PostgreSQL must remain version 17 for this volume layout; major database upgrades need a deliberate migration plan.

## Native development

Install Python 3.13 and Node 22 first. Use an existing PostgreSQL 17 server, or start only the database with Docker:

```powershell
Copy-Item .env.example .env
docker compose up -d db
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[test]'
Copy-Item .env backend/.env
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the project root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

If `py` is unavailable, use the full path to Python 3.13 to create the environment. On macOS/Linux use `python3.13`, `.venv/bin/python`, and `cp` instead of their PowerShell equivalents. Settings load `.env` from the backend process's working directory; environment variables take precedence. Native uploads default to `backend/.local/uploads` when running from `backend/`. The Vite proxy reads `API_PROXY_TARGET` from the root `.env` or the shell. Browser requests always use relative `/api` URLs. No CORS exceptions are required.

PostgreSQL is required: the application never switches to SQLite or another database if a connection fails. An API health response can succeed while database readiness fails.

## Configuration

Copy the example; never commit real credentials. The example password is for isolated local development. Change it before any broader use. Database passwords placed in a connection URL must be URL-encoded; use simple local credentials for Compose interpolation.

| Variable | Default / purpose |
| --- | --- |
| `POSTGRES_USER` | `thrive`; Compose database user |
| `POSTGRES_PASSWORD` | Required by Compose; example contains a local-only placeholder |
| `POSTGRES_DB` | `thrive`; Compose database name |
| `DATABASE_URL` | Native psycopg SQLAlchemy PostgreSQL URL; Compose sets its own URL using `db` as host |
| `UPLOAD_DIR` | Native `.local/uploads`; Compose `/uploads` in a named volume |
| `MAX_UPLOAD_BYTES` | `20971520` (20 MiB) per file |
| `MAX_ARCHIVE_BYTES` | `104857600` (100 MiB) total declared/uncompressed ZIP bytes |
| `MAX_ARCHIVE_ENTRIES` | `2000` ZIP members |
| `MAX_COMPRESSION_RATIO` | `100` per member |
| `API_PROXY_TARGET` | Native Vite proxy target, default `http://127.0.0.1:8000` |
| `TEST_DATABASE_URL` | Opt-in URL of a disposable PostgreSQL test database |

The multipart request cap is the file limit plus 64 KiB for envelope overhead. The Docker frontend's Nginx gateway additionally caps requests at 21 MiB; adjust `frontend/nginx.conf` and rebuild if raising the backend limit. Large, unusually compressed but legitimate workbooks may be rejected by the archive policy.

## Migrations and checks

Run backend commands from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m pytest -q
```

The PostgreSQL integration test is skipped unless `TEST_DATABASE_URL` is set. Create a **separate disposable database** first, such as `thrive_test`. Do not point this test at a database holding useful work. It applies the real migration, uploads twice, checks independent records and stored originals, reads metadata through HTTP, verifies persistence through a fresh connection, and deletes its own metadata afterward.

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://thrive:local-development-only@localhost:5432/thrive_test'
..\.venv\Scripts\python.exe -m pytest -q
```

From `frontend/`:

```powershell
npm ci
npm run typecheck
npm run build
```

GitHub Actions runs these checks with a real PostgreSQL service if this repository is later hosted there. This task does not publish or push anything. See [verification notes](docs/verification.md) for checks actually run in the scaffold environment.

## API and upload behavior

| Method / path | Purpose |
| --- | --- |
| `GET /api/health` | API process health; independent of PostgreSQL |
| `GET /api/ready` | Database connectivity and metadata-table readiness; 503 on failure |
| `POST /api/workbooks` | Multipart `file`; returns stored metadata with 201 |
| `GET /api/workbooks?offset=0&limit=50` | Newest uploads first; maximum page size 100 |
| `GET /api/workbooks/{id}` | Metadata, or 404 |

Metadata includes UUID, original filename, byte size, SHA-256, UTC upload timestamp, and status `stored`. That status means the original file and metadata were stored, **not** that calculations or workbook semantics were validated. The internal stored-file identifier is kept in the database and excluded from API responses. Errors use `{"error":{"code":"...","message":"..."}}`; filesystem paths and stack traces are not returned.

**Duplicates:** every accepted upload creates a new UUID and a separately stored original, even when filename and checksum match. SHA-256 identifies identical content; it is not a uniqueness constraint. There is no implicit overwrite or deduplication.

## Current limitations and reviewer questions

This is a local review scaffold, not a production-ready multi-user service. There is no authentication, authorization, antivirus scanning, download/deletion endpoint, workbook preview, background job processing, or domain calculation. XLSX validation checks basic package structure and known active content; it is not a comprehensive Office security scanner or semantic workbook validator. Uploaded files are never served directly to the browser.

The database and filesystem cannot share an atomic transaction. Handled write/database failures roll back metadata and remove the new file. A process kill, power failure, ambiguous network failure during commit, or failed filesystem cleanup can still require reconciliation. Back up database and files together. See [architecture](docs/architecture.md) for boundaries and follow-up considerations.

Questions for John:

- Are the API, service, and persistence boundaries small and clear enough?
- Does the metadata/API design suit review and future workbook comparisons?
- Are duplicate behavior, file handling, and security limits appropriate?
- Which failure cases and integration tests should be strengthened first?
- What is the next smallest useful milestone: workbook inventory/inspection, or a narrowly specified calculation with a trusted reference fixture?
