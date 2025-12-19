"""add_api_fipe_extraction_method

Revision ID: 025
Revises: 024
Create Date: 2025-12-19

Adiciona o valor API_FIPE ao enum ExtractionMethod
Usado quando o preco e obtido via consulta direta a API Tabela FIPE
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar o valor API_FIPE ao enum extractionmethod
    # No PostgreSQL, precisamos usar ALTER TYPE
    op.execute("ALTER TYPE extractionmethod ADD VALUE IF NOT EXISTS 'API_FIPE'")


def downgrade():
    # Nao e possivel remover um valor de um enum no PostgreSQL de forma simples
    # Seria necessario recriar o enum e todas as colunas que o usam
    # Por seguranca, apenas passamos aqui
    pass
