# Thrive 2050

A local application for managing carbon projects and their Excel workbooks. Users can select a project and module, download a versioned Excel intake template, upload a completed template, and see validation feedback. Carbon calculations are not yet implemented.

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

- Create and select projects
- Upload `.xlsx` files and view file metadata
- Support methodology and version assignment; the methodology catalogue is currently empty
- Select the Workbook Intake utility, download its English Excel template, and upload it for version, layout, and required-cell checks
- Show cell-level errors for invalid templates and persist the version and validation status of accepted templates

Original workbooks can still be stored without the template. Template checks apply only when the **Completed intake template** file role is selected. This utility does not validate carbon data or produce calculations. Workbook previews, formula evaluation, carbon calculations, and calculation reports are not yet available.

## Local Setup

Install Docker, then run from the project root:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- Application: http://localhost:5173
- API documentation: http://localhost:8000/docs

This version is intended for local development and review. Authentication and user permissions are not yet implemented.
