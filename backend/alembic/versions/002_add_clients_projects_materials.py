"""add clients, projects, materials, items

Revision ID: 002
Revises: 001
Create Date: 2025-12-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clients table
    op.create_table('clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nome', sa.String(length=300), nullable=False),
        sa.Column('nome_curto', sa.String(length=100), nullable=True),
        sa.Column('cnpj', sa.String(length=20), nullable=True),
        sa.Column('tipo_orgao', sa.String(length=100), nullable=True),
        sa.Column('esfera', sa.String(length=50), nullable=True),
        sa.Column('endereco', sa.Text(), nullable=True),
        sa.Column('cidade', sa.String(length=100), nullable=True),
        sa.Column('uf', sa.String(length=2), nullable=True),
        sa.Column('cep', sa.String(length=10), nullable=True),
        sa.Column('telefone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('responsavel', sa.String(length=200), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=True, default=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clients_id'), 'clients', ['id'], unique=False)
    op.create_index(op.f('ix_clients_nome'), 'clients', ['nome'], unique=False)
    op.create_index(op.f('ix_clients_cnpj'), 'clients', ['cnpj'], unique=True)

    # Projects table
    op.create_table('projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=300), nullable=False),
        sa.Column('codigo', sa.String(length=50), nullable=True),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('numero_contrato', sa.String(length=100), nullable=True),
        sa.Column('numero_processo', sa.String(length=100), nullable=True),
        sa.Column('modalidade_licitacao', sa.String(length=100), nullable=True),
        sa.Column('data_inicio', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_previsao_fim', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_fim', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valor_contrato', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('status', sa.Enum('PLANEJAMENTO', 'EM_ANDAMENTO', 'CONCLUIDO', 'CANCELADO', 'SUSPENSO', name='projectstatus'), nullable=True),
        sa.Column('responsavel_tecnico', sa.String(length=200), nullable=True),
        sa.Column('responsavel_cliente', sa.String(length=200), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
    op.create_index(op.f('ix_projects_nome'), 'projects', ['nome'], unique=False)
    op.create_index(op.f('ix_projects_codigo'), 'projects', ['codigo'], unique=True)
    op.create_index(op.f('ix_projects_client_id'), 'projects', ['client_id'], unique=False)

    # Add project_id to quote_requests
    op.add_column('quote_requests', sa.Column('project_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_quote_requests_project_id', 'quote_requests', 'projects', ['project_id'], ['id'])
    op.create_index(op.f('ix_quote_requests_project_id'), 'quote_requests', ['project_id'], unique=False)

    # Characteristic types table
    op.create_table('characteristic_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('escopo', sa.Enum('GENERICA', 'ESPECIFICA', name='characteristicscope'), nullable=True),
        sa.Column('tipo_dado', sa.String(length=50), nullable=True, default='texto'),
        sa.Column('tipo_material_especifico', sa.String(length=100), nullable=True),
        sa.Column('valor_unico', sa.Boolean(), nullable=True, default=False),
        sa.Column('ativo', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_characteristic_types_id'), 'characteristic_types', ['id'], unique=False)
    op.create_index(op.f('ix_characteristic_types_nome'), 'characteristic_types', ['nome'], unique=True)

    # Materials table
    op.create_table('materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('codigo', sa.String(length=50), nullable=True),
        sa.Column('nome', sa.String(length=300), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('categoria', sa.String(length=100), nullable=True),
        sa.Column('subcategoria', sa.String(length=100), nullable=True),
        sa.Column('tipo', sa.String(length=100), nullable=True),
        sa.Column('marca', sa.String(length=100), nullable=True),
        sa.Column('fabricante', sa.String(length=200), nullable=True),
        sa.Column('unidade', sa.String(length=20), nullable=True, default='UN'),
        sa.Column('ativo', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_materials_id'), 'materials', ['id'], unique=False)
    op.create_index(op.f('ix_materials_nome'), 'materials', ['nome'], unique=False)
    op.create_index(op.f('ix_materials_codigo'), 'materials', ['codigo'], unique=True)
    op.create_index(op.f('ix_materials_categoria'), 'materials', ['categoria'], unique=False)

    # Material characteristics table
    op.create_table('material_characteristics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('tipo_id', sa.Integer(), nullable=False),
        sa.Column('valor', sa.Text(), nullable=False),
        sa.Column('obrigatorio', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ),
        sa.ForeignKeyConstraint(['tipo_id'], ['characteristic_types.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_material_characteristics_id'), 'material_characteristics', ['id'], unique=False)
    op.create_index(op.f('ix_material_characteristics_material_id'), 'material_characteristics', ['material_id'], unique=False)
    op.create_index(op.f('ix_material_characteristics_tipo_id'), 'material_characteristics', ['tipo_id'], unique=False)

    # Items table
    op.create_table('items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=100), nullable=True),
        sa.Column('patrimonio', sa.String(length=50), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, default='DISPONIVEL'),
        sa.Column('localizacao', sa.String(length=200), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_items_id'), 'items', ['id'], unique=False)
    op.create_index(op.f('ix_items_codigo'), 'items', ['codigo'], unique=False)
    op.create_index(op.f('ix_items_patrimonio'), 'items', ['patrimonio'], unique=True)
    op.create_index(op.f('ix_items_material_id'), 'items', ['material_id'], unique=False)
    op.create_index(op.f('ix_items_project_id'), 'items', ['project_id'], unique=False)

    # Item characteristics table
    op.create_table('item_characteristics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('tipo_id', sa.Integer(), nullable=False),
        sa.Column('valor', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
        sa.ForeignKeyConstraint(['tipo_id'], ['characteristic_types.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_item_characteristics_id'), 'item_characteristics', ['id'], unique=False)
    op.create_index(op.f('ix_item_characteristics_item_id'), 'item_characteristics', ['item_id'], unique=False)
    op.create_index(op.f('ix_item_characteristics_tipo_id'), 'item_characteristics', ['tipo_id'], unique=False)


def downgrade() -> None:
    # Drop item_characteristics
    op.drop_index(op.f('ix_item_characteristics_tipo_id'), table_name='item_characteristics')
    op.drop_index(op.f('ix_item_characteristics_item_id'), table_name='item_characteristics')
    op.drop_index(op.f('ix_item_characteristics_id'), table_name='item_characteristics')
    op.drop_table('item_characteristics')

    # Drop items
    op.drop_index(op.f('ix_items_project_id'), table_name='items')
    op.drop_index(op.f('ix_items_material_id'), table_name='items')
    op.drop_index(op.f('ix_items_patrimonio'), table_name='items')
    op.drop_index(op.f('ix_items_codigo'), table_name='items')
    op.drop_index(op.f('ix_items_id'), table_name='items')
    op.drop_table('items')

    # Drop material_characteristics
    op.drop_index(op.f('ix_material_characteristics_tipo_id'), table_name='material_characteristics')
    op.drop_index(op.f('ix_material_characteristics_material_id'), table_name='material_characteristics')
    op.drop_index(op.f('ix_material_characteristics_id'), table_name='material_characteristics')
    op.drop_table('material_characteristics')

    # Drop materials
    op.drop_index(op.f('ix_materials_categoria'), table_name='materials')
    op.drop_index(op.f('ix_materials_codigo'), table_name='materials')
    op.drop_index(op.f('ix_materials_nome'), table_name='materials')
    op.drop_index(op.f('ix_materials_id'), table_name='materials')
    op.drop_table('materials')

    # Drop characteristic_types
    op.drop_index(op.f('ix_characteristic_types_nome'), table_name='characteristic_types')
    op.drop_index(op.f('ix_characteristic_types_id'), table_name='characteristic_types')
    op.drop_table('characteristic_types')

    # Remove project_id from quote_requests
    op.drop_index(op.f('ix_quote_requests_project_id'), table_name='quote_requests')
    op.drop_constraint('fk_quote_requests_project_id', 'quote_requests', type_='foreignkey')
    op.drop_column('quote_requests', 'project_id')

    # Drop projects
    op.drop_index(op.f('ix_projects_client_id'), table_name='projects')
    op.drop_index(op.f('ix_projects_codigo'), table_name='projects')
    op.drop_index(op.f('ix_projects_nome'), table_name='projects')
    op.drop_index(op.f('ix_projects_id'), table_name='projects')
    op.drop_table('projects')

    # Drop clients
    op.drop_index(op.f('ix_clients_cnpj'), table_name='clients')
    op.drop_index(op.f('ix_clients_nome'), table_name='clients')
    op.drop_index(op.f('ix_clients_id'), table_name='clients')
    op.drop_table('clients')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS projectstatus')
    op.execute('DROP TYPE IF EXISTS characteristicscope')
