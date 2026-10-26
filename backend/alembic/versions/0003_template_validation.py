"""Record the exact template version validated at upload."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workbooks", sa.Column("template_version", sa.String(64)))
    op.add_column("workbooks", sa.Column("template_validation", sa.String(32)))
    op.create_check_constraint("ck_workbook_template_validation", "workbooks",
                               "(template_version IS NULL AND template_validation IS NULL) OR "
                               "(template_version IS NOT NULL AND template_validation = 'passed')")


def downgrade():
    op.drop_constraint("ck_workbook_template_validation", "workbooks", type_="check")
    op.drop_column("workbooks", "template_validation")
    op.drop_column("workbooks", "template_version")
