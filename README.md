# Thrive 2050

A local review foundation for reproducing carbon-project calculations across projects, methodology versions and workbook layouts. Working features are project creation/selection, catalogue-based methodology assignment, module compatibility filtering, and project-owned workbook intake. This scaffold is intended for John to review before calculation work begins. It does **not** implement Leakage, Biomass, Matching, ExPost, ExAnte, carbon accounting, formula evaluation, or methodology validation.

## Working workflow and scope

1. Create or select a project. Project identity is separate from methodological rules.
2. Leave methodology unassigned while collecting files, or select an exact code-configured identifier/version. **The initial methodology catalogue is intentionally empty**: no verified official versions were supplied. Arbitrary identifiers are rejected by the API. Catalogue review is separate from implemented calculation support.
3. Select generic project intake or **Workbook Intake 1.0.0**, a methodology-independent utility for storage. The utility defines an optional `original-workbook` role, not an official methodology requirement. Exact module-version/file-role associations are recorded when selected.
4. Upload `.xlsx` files and inspect metadata. The UI distinguishes basic XLSX checks from domain-input validation, which has not been performed.
5. Extracted-input review, calculation execution and results remain explicitly unavailable in the UI. API review/run requests return errors, never simulated success.

Module availability is `unavailable`, `file_intake_only`, or `calculation_ready`. There are **no calculation-ready modules**. The registry rejects ready registrations until an execution contract is implemented. No result or run tables are created for unavailable features.

Migration `0002` preserves existing metadata, checksums, timestamps and stored-file IDs. It assigns earlier uploads to **Legacy workbook collection**, which explicitly does not claim a real-world project identity or methodology. Original bytes are not moved or read by the migration. The old `/api/workbooks` routes remain deprecated compatibility endpoints scoped only to that collection; new work uses project-scoped routes. There is no file-reassignment endpoint.

Existing `code/`, `data/`, and reference-document folders were preserved. The application lives at the repository root; existing workbook and reference folders are excluded from version control. No existing workbook is automatically imported.

## Stack and requirements

- React 19 and TypeScript: reusable upload and metadata interfaces with explicit data contracts.
- Vite 8: a small development server with an API proxy and a production build. Use Node **22.22.2+ on the 22 LTS line** or **24.15+ on the 24 LTS line**. The test toolchain needs this minimum. npm 10+; `frontend/package-lock.json` records exact dependencies.
- Python **3.12–3.14**, with **3.13 recommended**; FastAPI provides HTTP validation and OpenAPI documentation.
- SQLAlchemy 2 and psycopg 3: explicit PostgreSQL persistence. Alembic owns schema changes; startup does not call `create_all`.
- PostgreSQL **17** and Docker Compose v2 for local infrastructure. Python dependencies are defined in `backend/pyproject.toml` and resolved in `backend/uv.lock`. Docker, CI and the native workflow use uv **0.13.5** and enforce the lockfile. React suits reusable project, upload, metadata and future comparison interfaces; runtime API responses are independently checked with Zod.

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

Install Python 3.13 and the required Node 22 version first. Use an existing PostgreSQL 17 server, or start only the database with Docker:

```powershell
Copy-Item .env.example .env
docker compose up -d db
py -3.13 -m pip install uv==0.13.5
py -3.13 -m uv sync --project backend --locked --extra test --python 3.13
Copy-Item .env backend/.env
Set-Location backend
py -3.13 -m uv run --locked --extra test alembic upgrade head
py -3.13 -m uv run --locked --extra test uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the project root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

If `py` is unavailable, replace `py -3.13` with the full path to Python 3.13 in each command. On macOS/Linux replace `py -3.13` with `python3.13` and use `cp` instead of `Copy-Item`. uv creates the locked environment in `backend/.venv`; an older root `.venv` may remain ignored but is not used by this workflow. Settings load `.env` from the backend process's working directory; environment variables take precedence. Native uploads default to `backend/.local/uploads` when running from `backend/`. The Vite proxy reads `API_PROXY_TARGET` from the root `.env` or the shell. Browser requests always use relative `/api` URLs. No CORS exceptions are required.

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
py -3.13 -m uv sync --locked --extra test
py -3.13 -m uv run --locked --extra test alembic upgrade head
py -3.13 -m uv run --locked --extra test pytest -q
py -3.13 -m uv run --locked --extra test alembic check
```

PostgreSQL integration tests are skipped unless `TEST_DATABASE_URL` is set. Create a **separate disposable database** first, such as `thrive_test`. Do not point these tests at a database holding useful work. Tests apply real migrations, preserve pre-migration metadata, check project ownership and duplicates, reject unsupported combinations, and verify committed metadata and original bytes. Project tests create/drop isolated schemas and require schema-creation permission. The legacy API test also applies migrations in the test database's default schema and deletes its own uploaded metadata afterward.

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://thrive:local-development-only@localhost:5432/thrive_test'
py -3.13 -m uv run --locked --extra test pytest -q
```

From `frontend/`:

```powershell
npm ci
npm run typecheck
npm test
npm run build
```

Frontend component tests use explicitly mocked API responses to verify UI behavior; they do not claim to test database persistence. GitHub Actions runs backend checks with a real PostgreSQL service and frontend checks from the lockfile if this repository is later hosted there. This task does not publish or push anything. See [verification notes](docs/verification.md) for checks actually run in the scaffold environment. To update dependencies deliberately, run `uv lock --upgrade` in `backend/` or `npm update` in `frontend/`, then rerun all checks and review both lockfiles.

## API and upload behavior

| Method / path | Purpose |
| --- | --- |
| `GET /api/health` | API process health; independent of PostgreSQL |
| `GET /api/ready` | Database connectivity and metadata-table readiness; 503 on failure |
| `GET /api/catalogue` | Code-defined methodology versions and module definitions |
| `POST /api/projects` | Create a project with name, optional description and exact optional methodology pair |
| `GET /api/projects?offset=0&limit=50` | Paginated project list; maximum page size 100 |
| `GET /api/projects/{project_id}` | Selected project context |
| `PUT /api/projects/{project_id}/methodology` | Assign an exact configured pair or both null |
| `GET /api/projects/{project_id}/modules` | Compatible module versions, including unavailable entries with reasons |
| `POST /api/projects/{project_id}/workbooks` | Multipart `file`; optional `module_id`, `module_version`, `file_role` must be supplied together |
| `GET /api/projects/{project_id}/workbooks?offset=0&limit=50` | Files owned by this project only |
| `GET /api/projects/{project_id}/workbooks/{id}` | Project-scoped metadata; wrong-project IDs return 404 |
| `POST /api/projects/{project_id}/inputs/review` | Rejects unimplemented input review; no extraction occurs |
| `POST /api/projects/{project_id}/runs` | Rejects unimplemented execution; no run or results created |
| `/api/workbooks`, `/api/workbooks/{id}` | Deprecated original routes, restricted to the legacy collection |

Metadata includes UUID, owning project ID, optional module/version/role, original filename, byte size, SHA-256, UTC upload timestamp, status `stored`, `package_validation: basic_checks_passed`, and `domain_validation: not_performed`. The validation fields describe the intake gate, not a persisted domain-validation report. Successful intake means original bytes and metadata were stored after basic package checks, **not** that files are calculation-ready. The internal stored-file identifier is kept in the database and excluded from API responses. Errors use `{"error":{"code":"...","message":"..."}}`; filesystem paths and stack traces are not returned.

Methodology assignments cannot change once methodology-specific or unknown module associations exist. Known methodology-independent utility files allow later rule selection. Assignment changes and uploads lock the same project row to keep compatibility checks consistent under concurrency. Generic files do not imply any methodology suitability. PostgreSQL foreign keys require a valid owner, and check constraints require complete methodology/module context pairs. Project scoping protects workflow integrity; it is **not authorization** in this unauthenticated local scaffold.

**Duplicates:** every accepted upload creates a new UUID and a separately stored original, even when filename and checksum match. SHA-256 identifies identical content; it is not a uniqueness constraint. There is no implicit overwrite or deduplication.

## Current limitations and reviewer questions

This is a local review scaffold, not a production-ready multi-user service. There is no authentication, authorization, antivirus scanning, download/deletion endpoint, workbook preview, background job processing, or domain calculation. XLSX validation checks basic package structure and known active content; it is not a comprehensive Office security scanner or semantic workbook validator. Uploaded files are never served directly to the browser.

The database and filesystem cannot share an atomic transaction. Handled write/database failures roll back metadata and remove the new file. A process kill, power failure, ambiguous network failure during commit, or failed filesystem cleanup can still require reconciliation. Back up database and files together. See [architecture](docs/architecture.md) for boundaries and follow-up considerations.

Questions for John:

- Are the API, service, and persistence boundaries small and clear enough?
- Is the code-defined catalogue and exact-version compatibility model sufficiently simple?
- Does the metadata/API and database/file-storage design suit review and future workbook comparisons?
- Are duplicate behavior, file handling, and security limits appropriate?
- Which failure cases and integration tests should be strengthened first? Which security and scaling controls matter first?
- What is the next smallest useful milestone: workbook inventory/inspection, or a narrowly specified calculation with a trusted reference fixture?
