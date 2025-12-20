"""add batch result files

Revision ID: 028
Revises: 027
Create Date: 2025-12-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar colunas para arquivos de resultado do lote
    op.add_column('batch_quote_jobs', sa.Column('result_zip_path', sa.String(500), nullable=True))
    op.add_column('batch_quote_jobs', sa.Column('result_excel_path', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('batch_quote_jobs', 'result_excel_path')
    op.drop_column('batch_quote_jobs', 'result_zip_path')
