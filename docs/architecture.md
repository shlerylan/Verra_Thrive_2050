# Architecture for review

## Boundaries

```text
React + TypeScript (browser)
    -> /api (Vite proxy locally; Nginx in Compose)
    -> FastAPI routes and Pydantic response schemas
    -> workbook service (filename/package validation, checksum, storage)
    -> SQLAlchemy session -> PostgreSQL metadata
    -> private upload directory -> immutable original bytes
```

This is a modular monolith: one API process and one database, with a small static frontend. `app/api` translates HTTP; `app/schemas` defines public metadata; `app/services` owns the upload use case; `app/models` and `app/db` own persistence; `app/core` holds configuration and errors. Alembic changes the schema explicitly. There are no speculative calculation tables or extension frameworks.

React supports reusable forms, status messages, tables, and metadata panels that can later support comparison interfaces. TypeScript checks frontend data use at build time. Types alone do not validate network responses: Zod validates the API payload at runtime, and Pydantic validates backend responses. Changes to these parallel contracts should be reviewed together; generated client types can be considered once the API stabilizes.

The browser has real loading, unavailable, empty, success, and error states. API status checks process health; database failures appear as actionable library/upload errors. Metadata is fetched from its own endpoint. Pagination limits metadata queries. No results, metrics, or methodology claims are fabricated.

## Upload lifecycle

1. Limit the raw HTTP request before multipart parsing can spool unlimited data. Starlette may temporarily spool accepted multipart data to the operating-system temporary directory.
2. Validate the original filename; generate a UUID for private storage independent of the name.
3. Stream bytes into storage in 64 KiB chunks, enforcing size and computing SHA-256.
4. Inspect the ZIP in place without extraction. Bound member count, total expanded size, and per-member compression ratio; stream every member to verify CRC and actual sizes. Reject encryption, traversal, symlinks, duplicate members, malformed archives, known macro and embedded active content, and invalid required XML parts. Parse required XML with defusedxml to reject entity-based attacks.
5. Flush and refresh the new metadata, then commit. Return `stored` only after commit. Handled failures roll back and remove the new file, including failures during database flush/commit. Separate uploads always have separate records/files.

Synchronous route handlers run in FastAPI's thread pool, so ZIP parsing, hashing, filesystem writes, and synchronous SQLAlchemy calls do not run on the asynchronous event loop. The request body is bounded before parsing; the service also enforces the exact file limit. This is a small-file local design; it does not claim high concurrency or full Office-package validation. External links are not refreshed, formulas are not evaluated, and macros are never executed.

Metadata and original bytes have separate storage lifecycles. The application never stores uploads in the frontend public directory and exposes no download path. SQLAlchemy parameterizes database access. Public errors omit internal paths and exception details. Local ports bind only to loopback; API CORS is not opened.

## Consistency and testing

PostgreSQL is the only application database. Readiness checks connectivity and access to the metadata table, which catches missing initial migrations. No schema is automatically created at API startup. Compose explicitly runs Alembic before serving. Only one migration runner is intended in this local setup.

Pure tests cover package validation and filenames. Service failure tests inject database/storage failures to check cleanup; they do not claim to verify PostgreSQL transactions. HTTP tests cover readiness, consistent errors, and request-size enforcement. The opt-in integration test applies Alembic to a disposable PostgreSQL database and verifies real HTTP uploads, duplicate handling, committed metadata, and stored bytes. CI supplies PostgreSQL. Frontend type checking and a production build validate compilation; a manual browser/API smoke check verifies the proxy and UI together when runtimes are available.

The filesystem and database are not one atomic resource. Ordinary failures are compensated; abrupt termination or uncertain commit outcomes still need a reconciliation strategy. A production implementation should track durable upload state, reconcile missing/orphaned files, and test recovery procedures rather than promising perfect atomicity.

## Future work

Calculation logic should eventually be pure, independently tested modules, separate from HTTP handlers, Excel-reading adapters, and persistence. Start only after a reviewer supplies an explicit methodology and trusted input/output fixtures. Preserve provenance, units, and rounding rules when that work begins. No such calculations are included here.

Before multi-user deployment, review authentication, per-file authorization, tenancy, quotas, CSRF/origin protections appropriate to the chosen credentials, malware scanning, audit trails, TLS, secrets management, dependency patching, and backup/restore. Do not treat a loopback development deployment as a production security design. A user with access to the local host can access this unauthenticated API.

For larger files or concurrent usage, consider a bounded worker pool, isolated package inspection, direct object-storage uploads with validation states, durable jobs, and resource limits. Add infrastructure only when concrete workload and recovery requirements justify it. For deployment, build immutable images, restrict filesystem permissions, pin reviewed image/dependency versions, and coordinate migrations as a separate release step. PostgreSQL metadata and file storage must be backed up and restored consistently.

## Questions for reviewer

- Are these module boundaries sufficient for the next narrowly scoped feature?
- Should upload records gain explicit validation/recovery states before calculations begin?
- Is keeping duplicates useful for review, or should the API expose duplicate warnings?
- Which file-security policy and integration fixtures best reflect the real workbook collection?
- What is the smallest useful next milestone with an agreed acceptance test?
