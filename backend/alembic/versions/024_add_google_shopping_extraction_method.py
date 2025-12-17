"""add_google_shopping_extraction_method

Revision ID: 024
Revises: 023
Create Date: 2025-12-17

Adiciona o valor GOOGLE_SHOPPING ao enum ExtractionMethod
Usado quando enable_price_mismatch=False (fluxo Google Only)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar o valor GOOGLE_SHOPPING ao enum extractionmethod
    # No PostgreSQL, precisamos usar ALTER TYPE
    op.execute("ALTER TYPE extractionmethod ADD VALUE IF NOT EXISTS 'GOOGLE_SHOPPING'")


def downgrade():
    # Não é possível remover um valor de um enum no PostgreSQL de forma simples
    # Seria necessário recriar o enum e todas as colunas que o usam
    # Por segurança, apenas passamos aqui
    pass
