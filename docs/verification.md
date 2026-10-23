# Scaffold verification

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
