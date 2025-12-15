"""add check constraints

Revision ID: add_check_constraints
Revises: add_performance_indexes
Create Date: 2024-12-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_check_constraints'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """Adiciona constraints de validação"""

    # Constraint para progress_percentage (0-100)
    op.create_check_constraint(
        'ck_quote_requests_progress_percentage',
        'quote_requests',
        'progress_percentage >= 0 AND progress_percentage <= 100'
    )

    # Constraint para attempt_number (>= 1)
    op.create_check_constraint(
        'ck_quote_requests_attempt_number',
        'quote_requests',
        'attempt_number >= 1'
    )

    # Constraint para valores de cotação (devem ser positivos)
    op.create_check_constraint(
        'ck_quote_requests_valor_medio',
        'quote_requests',
        'valor_medio IS NULL OR valor_medio >= 0'
    )
    op.create_check_constraint(
        'ck_quote_requests_valor_minimo',
        'quote_requests',
        'valor_minimo IS NULL OR valor_minimo >= 0'
    )
    op.create_check_constraint(
        'ck_quote_requests_valor_maximo',
        'quote_requests',
        'valor_maximo IS NULL OR valor_maximo >= 0'
    )

    # Constraint para quote_sources (price_value deve ser positivo)
    op.create_check_constraint(
        'ck_quote_sources_price_value',
        'quote_sources',
        'price_value IS NULL OR price_value > 0'
    )

    # Constraint para bank_prices (vl_mercado deve ser positivo)
    op.create_check_constraint(
        'ck_bank_prices_vl_mercado',
        'bank_prices',
        'vl_mercado >= 0'
    )


def downgrade():
    """Remove as constraints adicionadas"""

    op.drop_constraint('ck_quote_requests_progress_percentage', 'quote_requests')
    op.drop_constraint('ck_quote_requests_attempt_number', 'quote_requests')
    op.drop_constraint('ck_quote_requests_valor_medio', 'quote_requests')
    op.drop_constraint('ck_quote_requests_valor_minimo', 'quote_requests')
    op.drop_constraint('ck_quote_requests_valor_maximo', 'quote_requests')
    op.drop_constraint('ck_quote_sources_price_value', 'quote_sources')
    op.drop_constraint('ck_bank_prices_vl_mercado', 'bank_prices')
