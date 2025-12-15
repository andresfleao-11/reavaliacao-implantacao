"""add_client_to_materials_and_items

Revision ID: 007
Revises: 006
Create Date: 2025-12-11

Adiciona:
- client_id em materials e items
- codigo numérico de 9 dígitos em materials
- índice de unicidade em items (client_id + material_id + hash de características)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar client_id em materials
    op.add_column('materials', sa.Column('client_id', sa.Integer(), nullable=True))

    # Alterar tamanho da coluna codigo (de 50 para 9 caracteres)
    op.alter_column('materials', 'codigo',
                    existing_type=sa.String(50),
                    type_=sa.String(9),
                    existing_nullable=True)

    # Criar foreign key para client_id em materials
    op.create_foreign_key('fk_materials_client', 'materials', 'clients', ['client_id'], ['id'])

    # Criar índice em client_id em materials (codigo já tem índice)
    op.create_index('ix_materials_client_id', 'materials', ['client_id'])

    # Adicionar client_id em items
    op.add_column('items', sa.Column('client_id', sa.Integer(), nullable=True))

    # Criar foreign key para client_id em items
    op.create_foreign_key('fk_items_client', 'items', 'clients', ['client_id'], ['id'])

    # Criar índice em client_id em items
    op.create_index('ix_items_client_id', 'items', ['client_id'])

    # Adicionar coluna para hash de características (para validação de unicidade)
    op.add_column('items', sa.Column('caracteristicas_hash', sa.String(64), nullable=True))
    op.create_index('ix_items_caracteristicas_hash', 'items', ['caracteristicas_hash'])

    # Criar índice composto para unicidade (client_id + material_id + caracteristicas_hash)
    op.create_index(
        'ix_items_uniqueness',
        'items',
        ['client_id', 'material_id', 'caracteristicas_hash'],
        unique=False  # Não unique porque podem ter valores NULL
    )


def downgrade():
    # Remover índices
    op.drop_index('ix_items_uniqueness', 'items')
    op.drop_index('ix_items_caracteristicas_hash', 'items')
    op.drop_index('ix_items_client_id', 'items')
    op.drop_index('ix_materials_client_id', 'materials')

    # Remover foreign keys
    op.drop_constraint('fk_items_client', 'items', type_='foreignkey')
    op.drop_constraint('fk_materials_client', 'materials', type_='foreignkey')

    # Reverter tamanho da coluna codigo
    op.alter_column('materials', 'codigo',
                    existing_type=sa.String(9),
                    type_=sa.String(50),
                    existing_nullable=True)

    # Remover colunas
    op.drop_column('items', 'caracteristicas_hash')
    op.drop_column('items', 'client_id')
    op.drop_column('materials', 'client_id')
