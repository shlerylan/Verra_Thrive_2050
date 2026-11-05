# Qinren X Thrive 2050

A local application for managing carbon projects and their Excel workbooks. Users can select a project and module, download a versioned Excel template, upload completed inputs, and see validation feedback. A limited agricultural Leakage calculation preview is available; verified carbon calculations are not yet implemented.

## Tech Stack

- **Frontend**: React 19, TypeScript, Vite 8
- **Backend**: Python, FastAPI
- **Database**: PostgreSQL 17, SQLAlchemy, Alembic
- **Local Deployment**: Docker Compose

## Basic Architecture

```text
Frontend
   ↓
FastAPI Backend
   ├── Module catalogue and template validation
   ├── PostgreSQL: project and file metadata
   └── File Storage: original Excel files
```

Files belong to individual projects. Uploads undergo basic format checks, and the system records the filename, size, upload time, and content checksum.

## Current Features

- Upload the Brazil Cerrado 1 sample or a completed template to compare annual production, land area and density, and explore leakage scenarios

- Follow a step-by-step flow: project → methodology → calculation → Excel inputs → results, with back navigation and project file history
- Create and select projects
- Upload `.xlsx` files and view file metadata
- Assign VM0047 v1.0 to a project and select a compatible module
- Select the Workbook Intake utility, download its English Excel template, and upload it for version, layout, and required-cell checks
- Show cell-level errors for invalid templates and persist the version and validation status of accepted templates
- Preview one-commodity agricultural Leakage arithmetic under VMD0054 v1.0 and download a text report

Original workbooks can still be stored without a template. The Leakage pilot validates its own input template and calculates an arithmetic preview; it does not verify source evidence or project eligibility. [Scope and limitations](docs/leakage-pilot.md). Workbook previews, formula evaluation, formal calculation runs, and verified reports are not yet available.

## Local Setup

Install Docker, then run from the project root:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- Application: http://localhost:5173
- API documentation: http://localhost:8000/docs

This version is intended for local development and review. Authentication and user permissions are not yet implemented.
