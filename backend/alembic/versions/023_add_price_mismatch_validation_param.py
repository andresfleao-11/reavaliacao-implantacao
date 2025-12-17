"""Add enable_price_mismatch_validation parameter

Revision ID: 023
Revises: 022
Create Date: 2025-12-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna enable_price_mismatch_validation
    op.add_column(
        'project_config_versions',
        sa.Column('enable_price_mismatch_validation', sa.Boolean(), nullable=True, server_default='true')
    )

    # Atualizar registros existentes para ter o valor padrão True
    op.execute("UPDATE project_config_versions SET enable_price_mismatch_validation = true WHERE enable_price_mismatch_validation IS NULL")


def downgrade():
    op.drop_column('project_config_versions', 'enable_price_mismatch_validation')
