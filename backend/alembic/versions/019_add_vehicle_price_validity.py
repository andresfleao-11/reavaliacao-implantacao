"""add vehicle price validity features

Revision ID: 019
Revises: 018
Create Date: 2024-12-16 01:30:00.000000

REQ-FIPE-003: Vigencia de Cotacao e Otimizacao do Banco de Precos de Veiculos
- Adiciona constraint UNIQUE para evitar duplicatas (codigo_fipe, year_id)
- Adiciona parametro vigencia_cotacao_veiculos em project_config_versions
- Adiciona indice otimizado para consulta de veiculos
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '019'
down_revision: Union[str, None] = '018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Remover duplicatas existentes antes de criar constraint
    # Manter apenas o registro mais recente para cada combinacao (codigo_fipe, year_id)
    op.execute("""
        DELETE FROM vehicle_price_bank a
        USING vehicle_price_bank b
        WHERE a.id < b.id
          AND a.codigo_fipe = b.codigo_fipe
          AND a.year_id = b.year_id
    """)

    # 2. Adicionar constraint UNIQUE para evitar duplicatas
    op.create_unique_constraint(
        'uq_vehicle_fipe_year',
        'vehicle_price_bank',
        ['codigo_fipe', 'year_id']
    )

    # 3. Adicionar indice otimizado para consulta de veiculos
    op.create_index(
        'idx_vehicle_lookup',
        'vehicle_price_bank',
        ['codigo_fipe', 'year_id', 'updated_at'],
        postgresql_ops={'updated_at': 'DESC'}
    )

    # 4. Adicionar parametro de vigencia em project_config_versions
    op.add_column(
        'project_config_versions',
        sa.Column('vigencia_cotacao_veiculos', sa.Integer(), nullable=True, server_default='6')
    )


def downgrade() -> None:
    # Remover parametro de vigencia
    op.drop_column('project_config_versions', 'vigencia_cotacao_veiculos')

    # Remover indice de lookup
    op.drop_index('idx_vehicle_lookup', table_name='vehicle_price_bank')

    # Remover constraint UNIQUE
    op.drop_constraint('uq_vehicle_fipe_year', 'vehicle_price_bank', type_='unique')
