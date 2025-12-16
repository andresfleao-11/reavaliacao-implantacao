"""add vehicle_price_bank table

Revision ID: 018
Revises: 017
Create Date: 2024-12-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '018'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Criar tabela de banco de precos de veiculos
    op.create_table(
        'vehicle_price_bank',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),

        # Identificadores FIPE
        sa.Column('codigo_fipe', sa.String(15), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('brand_name', sa.String(100), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(200), nullable=False),
        sa.Column('year_id', sa.String(10), nullable=False),
        sa.Column('year_model', sa.Integer(), nullable=False),
        sa.Column('fuel_type', sa.String(30), nullable=False),
        sa.Column('fuel_code', sa.Integer(), nullable=False),

        # Dados do Veiculo
        sa.Column('vehicle_type', sa.String(20), nullable=False, server_default='cars'),
        sa.Column('vehicle_name', sa.String(300), nullable=False),

        # Preco e Referencia
        sa.Column('price_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('reference_month', sa.String(30), nullable=False),
        sa.Column('reference_date', sa.Date(), nullable=False),

        # Rastreabilidade
        sa.Column('quote_request_id', sa.Integer(), nullable=True),
        sa.Column('api_response_json', sa.JSON(), nullable=True),
        sa.Column('last_api_call', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['quote_request_id'], ['quote_requests.id'], )
    )

    # Indices para busca rapida
    op.create_index('idx_vehicle_price_bank_codigo_fipe', 'vehicle_price_bank', ['codigo_fipe'])
    op.create_index('idx_vehicle_price_bank_brand_name', 'vehicle_price_bank', ['brand_name'])
    op.create_index('idx_vehicle_price_bank_year_model', 'vehicle_price_bank', ['year_model'])
    op.create_index('idx_vehicle_price_bank_reference_date', 'vehicle_price_bank', ['reference_date'])


def downgrade() -> None:
    op.drop_index('idx_vehicle_price_bank_reference_date')
    op.drop_index('idx_vehicle_price_bank_year_model')
    op.drop_index('idx_vehicle_price_bank_brand_name')
    op.drop_index('idx_vehicle_price_bank_codigo_fipe')
    op.drop_table('vehicle_price_bank')
