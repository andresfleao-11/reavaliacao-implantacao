"""Add characteristic options

Revision ID: 005
Revises: 004
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna de opções na tabela de características do material
    op.add_column('material_characteristics', sa.Column('opcoes_json', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('material_characteristics', 'opcoes_json')
