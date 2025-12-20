"""add checkpoint resume fields

Revision ID: 029
Revises: 028
Create Date: 2025-12-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade():
    # Campos para sistema de checkpoints e retomada
    op.add_column('quote_requests', sa.Column('processing_checkpoint', sa.String(50), nullable=True))
    op.add_column('quote_requests', sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True))
    op.add_column('quote_requests', sa.Column('worker_id', sa.String(100), nullable=True))
    op.add_column('quote_requests', sa.Column('resume_data', sa.JSON(), nullable=True))
    op.add_column('quote_requests', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('quote_requests', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

    # Indice para buscar cotacoes travadas (status PROCESSING com heartbeat antigo)
    op.create_index('ix_quote_requests_heartbeat_status', 'quote_requests', ['status', 'last_heartbeat'])

    # Indice para buscar por worker
    op.create_index('ix_quote_requests_worker_id', 'quote_requests', ['worker_id'])


def downgrade():
    op.drop_index('ix_quote_requests_worker_id', table_name='quote_requests')
    op.drop_index('ix_quote_requests_heartbeat_status', table_name='quote_requests')
    op.drop_column('quote_requests', 'completed_at')
    op.drop_column('quote_requests', 'started_at')
    op.drop_column('quote_requests', 'resume_data')
    op.drop_column('quote_requests', 'worker_id')
    op.drop_column('quote_requests', 'last_heartbeat')
    op.drop_column('quote_requests', 'processing_checkpoint')
