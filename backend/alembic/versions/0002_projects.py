"""Add project ownership without discarding or guessing the owners of existing uploads."""
from uuid import UUID
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
LEGACY_ID = UUID("00000000-0000-0000-0000-000000000001")


def upgrade():
    projects = op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("methodology_id", sa.String(100)),
        sa.Column("methodology_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(methodology_id IS NULL) = (methodology_version IS NULL)", name="ck_project_methodology_pair"),
    )
    op.bulk_insert(projects, [{"id": LEGACY_ID, "name": "Legacy workbook collection",
                              "description": "Preserved uploads from the original scaffold and legacy API. Ownership and methodology have not been established."}])
    op.add_column("workbooks", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.execute(sa.text("UPDATE workbooks SET project_id = :project_id").bindparams(project_id=LEGACY_ID))
    op.alter_column("workbooks", "project_id", nullable=False)
    op.create_foreign_key("fk_workbooks_project", "workbooks", "projects", ["project_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_workbooks_project_id", "workbooks", ["project_id"])
    op.add_column("workbooks", sa.Column("module_id", sa.String(100)))
    op.add_column("workbooks", sa.Column("module_version", sa.String(64)))
    op.add_column("workbooks", sa.Column("file_role", sa.String(100)))
    op.create_check_constraint("ck_workbook_module_context", "workbooks",
                               "(module_id IS NULL AND module_version IS NULL AND file_role IS NULL) OR "
                               "(module_id IS NOT NULL AND module_version IS NOT NULL AND file_role IS NOT NULL)")


def downgrade():
    op.drop_constraint("ck_workbook_module_context", "workbooks", type_="check")
    for name in ("file_role", "module_version", "module_id"):
        op.drop_column("workbooks", name)
    op.drop_index("ix_workbooks_project_id", table_name="workbooks")
    op.drop_constraint("fk_workbooks_project", "workbooks", type_="foreignkey")
    op.drop_column("workbooks", "project_id")
    op.drop_table("projects")
