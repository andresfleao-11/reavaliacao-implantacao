"""simplify materials and characteristics

Revision ID: 003
Revises: 002
Create Date: 2025-12-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Limpar dados existentes das tabelas de características (se houver)
    op.execute("DELETE FROM item_characteristics")
    op.execute("DELETE FROM material_characteristics")

    # Remover colunas antigas de material_characteristics
    op.drop_constraint('material_characteristics_tipo_id_fkey', 'material_characteristics', type_='foreignkey')
    op.drop_index('ix_material_characteristics_tipo_id', table_name='material_characteristics')
    op.drop_column('material_characteristics', 'tipo_id')
    op.drop_column('material_characteristics', 'valor')
    op.drop_column('material_characteristics', 'obrigatorio')

    # Adicionar novas colunas
    op.add_column('material_characteristics', sa.Column('nome', sa.String(100), nullable=False, server_default=''))
    op.add_column('material_characteristics', sa.Column('descricao', sa.Text(), nullable=True))
    op.add_column('material_characteristics', sa.Column('tipo_dado', sa.String(50), nullable=True, server_default='texto'))

    # Remover server_default após adicionar
    op.alter_column('material_characteristics', 'nome', server_default=None)
    op.alter_column('material_characteristics', 'tipo_dado', server_default=None)


def downgrade() -> None:
    # Reverter mudanças
    op.drop_column('material_characteristics', 'nome')
    op.drop_column('material_characteristics', 'descricao')
    op.drop_column('material_characteristics', 'tipo_dado')

    op.add_column('material_characteristics', sa.Column('tipo_id', sa.Integer(), nullable=True))
    op.add_column('material_characteristics', sa.Column('valor', sa.Text(), nullable=True))
    op.add_column('material_characteristics', sa.Column('obrigatorio', sa.Boolean(), nullable=True, default=False))

    op.create_index('ix_material_characteristics_tipo_id', 'material_characteristics', ['tipo_id'])
    op.create_foreign_key('material_characteristics_tipo_id_fkey', 'material_characteristics', 'characteristic_types', ['tipo_id'], ['id'])
