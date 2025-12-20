"""Add upload tracking fields to inventory_sessions

Revision ID: 032_add_session_upload_fields
Revises: 031_add_session_name_description
Create Date: 2024-12-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar campos de upload à tabela inventory_sessions
    op.add_column('inventory_sessions', sa.Column(
        'external_transmission_number',
        sa.String(100),
        nullable=True,
        comment='Número da transmissão retornado pelo sistema externo'
    ))
    op.add_column('inventory_sessions', sa.Column(
        'external_inventory_id',
        sa.String(100),
        nullable=True,
        comment='ID do levantamento no sistema externo'
    ))
    op.add_column('inventory_sessions', sa.Column(
        'external_uploaded_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='Data/hora do upload para o sistema externo'
    ))

    # Adicionar campos opcionais para controle do ASI
    op.add_column('inventory_sessions', sa.Column(
        'org_code',
        sa.String(20),
        nullable=True,
        comment='Código do órgão (para ASI)'
    ))
    op.add_column('inventory_sessions', sa.Column(
        'collector_id',
        sa.String(20),
        nullable=True,
        comment='ID do coletor/dispositivo'
    ))
    op.add_column('inventory_sessions', sa.Column(
        'objective_code',
        sa.String(20),
        nullable=True,
        default='01',
        comment='Código do objetivo do levantamento (ASI)'
    ))
    op.add_column('inventory_sessions', sa.Column(
        'responsible_code',
        sa.String(50),
        nullable=True,
        comment='Código do responsável no sistema externo'
    ))


def downgrade():
    op.drop_column('inventory_sessions', 'responsible_code')
    op.drop_column('inventory_sessions', 'objective_code')
    op.drop_column('inventory_sessions', 'collector_id')
    op.drop_column('inventory_sessions', 'org_code')
    op.drop_column('inventory_sessions', 'external_uploaded_at')
    op.drop_column('inventory_sessions', 'external_inventory_id')
    op.drop_column('inventory_sessions', 'external_transmission_number')
