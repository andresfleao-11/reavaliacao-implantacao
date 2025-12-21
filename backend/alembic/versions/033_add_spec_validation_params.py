"""Add spec validation and linear meter parameters

Revision ID: 033
Revises: 032
Create Date: 2025-12-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar parâmetros de validação de especificações
    op.add_column('project_config_versions', sa.Column(
        'enable_spec_extraction', sa.Boolean(), nullable=True, server_default='false'
    ))
    op.add_column('project_config_versions', sa.Column(
        'enable_spec_validation', sa.Boolean(), nullable=True, server_default='false'
    ))
    op.add_column('project_config_versions', sa.Column(
        'spec_dimension_tolerance', sa.Numeric(5, 2), nullable=True, server_default='0.20'
    ))

    # Adicionar parâmetros de metro linear
    op.add_column('project_config_versions', sa.Column(
        'enable_linear_meter', sa.Boolean(), nullable=True, server_default='false'
    ))
    op.add_column('project_config_versions', sa.Column(
        'linear_meter_min_products', sa.Integer(), nullable=True, server_default='2'
    ))


def downgrade():
    op.drop_column('project_config_versions', 'linear_meter_min_products')
    op.drop_column('project_config_versions', 'enable_linear_meter')
    op.drop_column('project_config_versions', 'spec_dimension_tolerance')
    op.drop_column('project_config_versions', 'enable_spec_validation')
    op.drop_column('project_config_versions', 'enable_spec_extraction')
