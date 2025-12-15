"""Add project config versions

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela de versões de configuração do projeto
    op.create_table(
        'project_config_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False, default=1),
        sa.Column('descricao_alteracao', sa.Text(), nullable=True),
        sa.Column('criado_por', sa.String(200), nullable=True),
        sa.Column('ativo', sa.Boolean(), default=True),

        # Parâmetros de busca SerpAPI
        sa.Column('serpapi_location', sa.String(200), nullable=True),
        sa.Column('serpapi_gl', sa.String(10), default='br'),
        sa.Column('serpapi_hl', sa.String(10), default='pt'),
        sa.Column('serpapi_num_results', sa.Integer(), default=10),
        sa.Column('search_timeout', sa.Integer(), default=30),
        sa.Column('max_sources', sa.Integer(), default=10),

        # Banco de Preços (JSON)
        sa.Column('banco_precos_json', sa.JSON(), nullable=True),

        # Fator de Reavaliação (JSON maps)
        sa.Column('ec_map_json', sa.JSON(), nullable=True),
        sa.Column('pu_map_json', sa.JSON(), nullable=True),
        sa.Column('vuf_map_json', sa.JSON(), nullable=True),
        sa.Column('weights_json', sa.JSON(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_project_config_versions_id', 'project_config_versions', ['id'])
    op.create_index('ix_project_config_versions_project_id', 'project_config_versions', ['project_id'])

    # Criar tabela de itens do banco de preços do projeto
    op.create_table(
        'project_bank_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('config_version_id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(100), nullable=False),
        sa.Column('material', sa.String(500), nullable=False),
        sa.Column('caracteristicas', sa.Text(), nullable=True),
        sa.Column('vl_mercado', sa.Numeric(12, 2), nullable=True),
        sa.Column('update_mode', sa.String(20), default='MARKET'),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['config_version_id'], ['project_config_versions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_project_bank_prices_id', 'project_bank_prices', ['id'])
    op.create_index('ix_project_bank_prices_config_version_id', 'project_bank_prices', ['config_version_id'])
    op.create_index('ix_project_bank_prices_codigo', 'project_bank_prices', ['codigo'])

    # Adicionar coluna de versão de configuração na tabela de cotações
    op.add_column('quote_requests', sa.Column('config_version_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_quote_requests_config_version',
        'quote_requests',
        'project_config_versions',
        ['config_version_id'],
        ['id']
    )
    op.create_index('ix_quote_requests_config_version_id', 'quote_requests', ['config_version_id'])


def downgrade():
    # Remover foreign key e coluna da tabela de cotações
    op.drop_index('ix_quote_requests_config_version_id', 'quote_requests')
    op.drop_constraint('fk_quote_requests_config_version', 'quote_requests', type_='foreignkey')
    op.drop_column('quote_requests', 'config_version_id')

    # Remover tabela de banco de preços do projeto
    op.drop_index('ix_project_bank_prices_codigo', 'project_bank_prices')
    op.drop_index('ix_project_bank_prices_config_version_id', 'project_bank_prices')
    op.drop_index('ix_project_bank_prices_id', 'project_bank_prices')
    op.drop_table('project_bank_prices')

    # Remover tabela de versões de configuração
    op.drop_index('ix_project_config_versions_project_id', 'project_config_versions')
    op.drop_index('ix_project_config_versions_id', 'project_config_versions')
    op.drop_table('project_config_versions')
