"""add integration logs table

Revision ID: 013
Revises: 012
Create Date: 2025-12-12 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela de logs de integração
    op.create_table(
        'integration_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_request_id', sa.Integer(), nullable=False),
        sa.Column('integration_type', sa.String(50), nullable=False),

        # Campos para Anthropic
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_cost_usd', sa.Numeric(10, 6), nullable=True),

        # Campos para SerpAPI
        sa.Column('api_used', sa.String(100), nullable=True),
        sa.Column('search_url', sa.Text(), nullable=True),

        # Campos comuns
        sa.Column('activity', sa.Text(), nullable=True),
        sa.Column('request_data', sa.JSON(), nullable=True),
        sa.Column('response_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['quote_request_id'], ['quote_requests.id'], ondelete='CASCADE')
    )

    # Criar índices
    op.create_index('ix_integration_logs_id', 'integration_logs', ['id'])
    op.create_index('ix_integration_logs_quote_request_id', 'integration_logs', ['quote_request_id'])
    op.create_index('ix_integration_logs_integration_type', 'integration_logs', ['integration_type'])
    op.create_index('ix_integration_logs_created_at', 'integration_logs', ['created_at'])


def downgrade():
    op.drop_index('ix_integration_logs_created_at', table_name='integration_logs')
    op.drop_index('ix_integration_logs_integration_type', table_name='integration_logs')
    op.drop_index('ix_integration_logs_quote_request_id', table_name='integration_logs')
    op.drop_index('ix_integration_logs_id', table_name='integration_logs')
    op.drop_table('integration_logs')
