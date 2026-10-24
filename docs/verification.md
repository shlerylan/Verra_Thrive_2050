# Scaffold verification

## Project-workflow milestone: 24 October 2026

The project workflow extends the earlier scaffold. Checks below use real PostgreSQL 17 on the existing disposable, loopback-only cluster and Python 3.13.7. Backend checks were rerun after installing from the new `backend/uv.lock` with uv 0.13.5. The frontend uses portable Node 22.23.4; its newer test dependencies require Node 22.22.2+ (or the documented newer LTS line). The system Node 20 installation was not modified.

| Check | Result |
| --- | --- |
| Locked backend `pytest -q` with real PostgreSQL | 38 passed |
| Migration-preservation test | `0001` metadata retained exactly through `0002`, assigned to the explicit legacy collection |
| Real database ownership/integrity | Cross-project metadata returns 404; foreign keys reject nonexistent owners; partial module context rejected |
| Catalogue and workflow tests | Exact-version compatibility, unknown methodology/module rejection, role checks, assignment guards and unavailable execution/review passed |
| Existing upload tests | Type, unsafe filename, malformed/active package, size/expansion limits, cleanup and duplicates still pass |
| `alembic check` | No new upgrade operations detected |
| Frontend checks | Clean `npm ci`, TypeScript and production build passed; 5 component tests verify project switching, delayed-response isolation, creation, role-bound intake, unavailable actions and retryable errors |
| Real Vite proxy smoke | Project creation/selection, catalogue, scoped upload/list/metadata, wrong-project denial, unknown methodology rejection, and explicit unavailable calculation/review passed |

Frontend tests explicitly mock API responses to inspect UI behavior. PostgreSQL integration tests and the real HTTP proxy smoke use actual database persistence. Synthetic methodology and module fixtures are test-only; the production methodology catalogue remains empty, with no calculation-ready modules. No actual project workbook was imported or used as a test fixture.

Docker is still unavailable, so image builds, Compose startup and production Nginx routing have not been executed. Browser automation again returned no browsers, so visual browser/keyboard interaction is unverified. GitHub Actions has been updated but not run remotely. The Starlette test-client httpx deprecation warning remains nonfatal.

The original scaffold verification below is retained as historical evidence; its Node 20 runtime instructions are superseded by the current README. All dependency/environment directories, portable test tools, test uploads, credentials and existing workbooks are ignored and excluded from the local commit.

## Initial scaffold: 23 October 2026

Verified locally on 23 October 2026 (Windows, Python 3.13.7, Node 20.19.5, npm 10.8.2).

| Check | Result |
| --- | --- |
| Backend `pytest -q`, initially without a database | 28 passed; 1 PostgreSQL test explicitly skipped |
| Full backend `pytest -q` with disposable PostgreSQL 17 | 29 passed, including real migration, upload persistence and duplicates |
| `alembic check` against migrated PostgreSQL | No new upgrade operations detected |
| `pip check` | No broken requirements |
| Clean `npm ci` using the delivered lockfile | Passed; npm reported zero known vulnerabilities at execution time |
| `npm run typecheck` | Passed |
| `npm run build` | Passed (Vite 8.3.5) |
| Real HTTP smoke through Vite on port 5173 | Page/module serving, API health/readiness, upload, list, metadata and invalid-package error passed |
| Real PostgreSQL outage and restart | Health stayed 200; readiness/list returned safe 503 errors; readiness recovered to 200 |

Docker and PostgreSQL were not installed on PATH. A portable PostgreSQL 17 test runtime was downloaded from the npm registry into ignored `.local/pg-tools`; a disposable cluster listened only on `127.0.0.1:55432`. The test used real PostgreSQL, not SQLite or mock persistence. Synthetic package fixtures contain no project calculations or results. No existing workbook was uploaded or modified.

The initial dependency installation was blocked by sandbox permissions and then by an npm 10 resolver bug. A temporary npm 11 invocation generated the lockfile. A subsequent ordinary npm 10 `npm ci` succeeded. Python and Node checks required execution outside the filesystem sandbox because the installed runtime/user-profile paths were inaccessible within it.

Not executed: Docker image builds, Compose startup, production Nginx routing, GitHub Actions, and browser visual/interaction checks. Docker is unavailable, and browser automation reported no available browsers. The proxy smoke test uses real HTTP requests and does not claim visual browser verification. CI configuration is provided but has not been run on GitHub as part of this local-only task.

The installed Starlette test client emits a deprecation warning about its httpx transport; tests pass. This test dependency should be revisited with the next dependency update. Dependency ranges in `pyproject.toml` should be rechecked when resolved to newer versions. Backend dependencies were checked with `pip check`; this is not a vulnerability audit.

Source, ignore rules, and the staged file manifest were reviewed before the local scaffold commit. Original workbooks/reference documents, `.env`, virtual environments, upload storage, portable database files, `node_modules`, and build output are excluded. The existing project/reference folders were preserved. No remote was configured and nothing was pushed or deployed.
