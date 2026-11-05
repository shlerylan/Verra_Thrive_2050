import hashlib
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4
from defusedxml import ElementTree
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.core.errors import AppError
from app.models.workbook import Workbook
from app.models.project import LEGACY_PROJECT_ID
from app.services.templates import FILE_ROLE, MODULE_ID, MODULE_VERSION, TEMPLATE_VERSION, validate_intake_template
from app.services import leakage

CONTENT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
WORKBOOK_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


def validate_filename(name: str | None) -> str:
    if (not name or len(name) > 255 or name != name.strip()
            or re.search(r'[<>:"/\\|?*\x00-\x1f\x7f]', name)
            or name.startswith(".") or not name.lower().endswith(".xlsx")):
        raise AppError(400, "invalid_filename", "Use a plain filename ending in .xlsx, without paths or special characters.")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise AppError(400, "invalid_filename", "This filename is reserved.")
    return name


def validate_package(path: Path, settings: Settings) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > settings.max_archive_entries:
                raise ValueError("Too many entries")
            names = set()
            total = 0
            xml = {}
            for entry in entries:
                name = entry.filename
                parts = PurePosixPath(name).parts
                if (name in names or name.startswith("/") or ".." in parts or "\\" in name
                        or ":" in name or entry.flag_bits & 1
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise ValueError("Unsafe archive entry")
                names.add(name)
                total += entry.file_size
                if (total > settings.max_archive_bytes
                        or entry.file_size > max(entry.compress_size, 1) * settings.max_compression_ratio):
                    raise ValueError("Archive expansion limit")
                if any(token in name.lower() for token in ("vbaproject", "vbasignature", "macrosheets/", "activex/", "embeddings/")):
                    raise ValueError("Active content")
                # Read every member to verify CRC and actual expansion; never extract it.
                actual = 0
                chunks = []
                with archive.open(entry) as member:
                    while chunk := member.read(64 * 1024):
                        actual += len(chunk)
                        if actual > entry.file_size or actual > settings.max_archive_bytes:
                            raise ValueError("Archive expansion limit")
                        if name in {"[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"}:
                            chunks.append(chunk)
                if chunks:
                    xml[name] = ElementTree.fromstring(b"".join(chunks))
            if not {"[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"} <= xml.keys():
                raise ValueError("Missing XLSX parts")
            types = xml["[Content_Types].xml"]
            if types.tag != CONTENT_NS + "Types":
                raise ValueError("Invalid content types")
            for item in types:
                content_type = item.get("ContentType", "").lower()
                if any(token in content_type for token in ("macro", "vba", "activex", "oleobject")):
                    raise ValueError("Active content")
            if not any(item.get("PartName") == "/xl/workbook.xml" and item.get("ContentType") == WORKBOOK_TYPE for item in types):
                raise ValueError("Invalid workbook type")
            if xml["xl/workbook.xml"].tag != SHEET_NS + "workbook":
                raise ValueError("Invalid workbook XML")
            relationship_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
            if not any(item.tag == relationship_ns + "Relationship"
                       and item.get("Type", "").endswith("/officeDocument")
                       and item.get("Target", "").lstrip("/") == "xl/workbook.xml"
                       and item.get("TargetMode") != "External" for item in xml["_rels/.rels"]):
                raise ValueError("Invalid root relationship")
    except AppError:
        raise
    except Exception as exc:
        raise AppError(400, "invalid_xlsx", "The file is not a supported, safe XLSX package or exceeds archive limits.") from exc


def store_workbook(source, filename: str | None, session: Session, settings: Settings, *,
                   project_id: UUID = LEGACY_PROJECT_ID, module_id: str | None = None,
                   module_version: str | None = None, file_role: str | None = None) -> Workbook:
    name = validate_filename(filename)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored_id = str(uuid4())
    path = settings.upload_dir / stored_id
    try:
        digest = hashlib.sha256()
        size = 0
        with path.open("xb") as target:
            while chunk := source.read(64 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise AppError(413, "upload_too_large", "The workbook exceeds the configured upload limit.")
                digest.update(chunk)
                target.write(chunk)
        validate_package(path, settings)
        is_intake = (module_id, module_version, file_role) == (MODULE_ID, MODULE_VERSION, FILE_ROLE)
        is_leakage = (module_id, module_version, file_role) == (leakage.MODULE_ID, leakage.MODULE_VERSION, leakage.FILE_ROLE)
        if is_intake:
            validate_intake_template(path)
        if is_leakage:
            leakage.parse_leakage_template(path)
        template_version = TEMPLATE_VERSION if is_intake else leakage.leakage_template_version(path) if is_leakage else None
        record = Workbook(original_filename=name, byte_size=size, sha256=digest.hexdigest(), stored_file_id=stored_id,
                          project_id=project_id, module_id=module_id, module_version=module_version, file_role=file_role,
                          template_version=template_version,
                          template_validation="passed" if template_version else None)
        session.add(record)
        session.flush()
        session.refresh(record)
        session.commit()
        return record
    except Exception:
        try:
            session.rollback()
        finally:
            path.unlink(missing_ok=True)
        raise
