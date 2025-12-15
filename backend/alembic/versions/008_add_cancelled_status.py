"""add_cancelled_status

Revision ID: 008
Revises: 007
Create Date: 2025-12-11

Adiciona o status CANCELLED ao enum QuoteStatus
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar o valor CANCELLED ao enum quotestatus
    # No PostgreSQL, precisamos usar ALTER TYPE
    op.execute("ALTER TYPE quotestatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade():
    # Não é possível remover um valor de um enum no PostgreSQL de forma simples
    # Seria necessário recriar o enum e todas as colunas que o usam
    # Por segurança, apenas passamos aqui
    pass
