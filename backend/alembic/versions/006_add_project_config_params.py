"""Add project config parameters

Revision ID: 006
Revises: 005
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar parâmetros de cotação na tabela de versões de configuração do projeto
    op.add_column('project_config_versions', sa.Column('numero_cotacoes_por_pesquisa', sa.Integer(), nullable=True))
    op.add_column('project_config_versions', sa.Column('max_cotacoes_armazenadas_por_item', sa.Integer(), nullable=True))
    op.add_column('project_config_versions', sa.Column('tolerancia_outlier_percent', sa.Numeric(5, 2), nullable=True))
    op.add_column('project_config_versions', sa.Column('tolerancia_variacao_vs_banco_percent', sa.Numeric(5, 2), nullable=True))
    op.add_column('project_config_versions', sa.Column('pesquisador_padrao', sa.String(200), nullable=True))
    op.add_column('project_config_versions', sa.Column('local_padrao', sa.String(200), nullable=True))


def downgrade():
    op.drop_column('project_config_versions', 'local_padrao')
    op.drop_column('project_config_versions', 'pesquisador_padrao')
    op.drop_column('project_config_versions', 'tolerancia_variacao_vs_banco_percent')
    op.drop_column('project_config_versions', 'tolerancia_outlier_percent')
    op.drop_column('project_config_versions', 'max_cotacoes_armazenadas_por_item')
    op.drop_column('project_config_versions', 'numero_cotacoes_por_pesquisa')
