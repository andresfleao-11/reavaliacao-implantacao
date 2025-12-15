"""Rename tolerancia_outlier_percent to variacao_maxima_percent

Revision ID: 015_rename_outlier_to_variacao
Revises: 014_add_variacao_percentual
Create Date: 2025-12-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade():
    # Rename column in project_config_versions table
    op.alter_column('project_config_versions', 'tolerancia_outlier_percent',
                    new_column_name='variacao_maxima_percent',
                    existing_type=sa.Numeric(5, 2),
                    existing_nullable=True)


def downgrade():
    op.alter_column('project_config_versions', 'variacao_maxima_percent',
                    new_column_name='tolerancia_outlier_percent',
                    existing_type=sa.Numeric(5, 2),
                    existing_nullable=True)
