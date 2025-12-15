"""add_progress_tracking_to_quote_requests

Revision ID: 915122f32fed
Revises: 010
Create Date: 2025-12-12 10:59:49.819934

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '915122f32fed'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adicionar campos de progresso
    op.add_column('quote_requests', sa.Column('current_step', sa.String(100), nullable=True))
    op.add_column('quote_requests', sa.Column('progress_percentage', sa.Integer, default=0))
    op.add_column('quote_requests', sa.Column('step_details', sa.Text, nullable=True))


def downgrade() -> None:
    # Remover campos de progresso
    op.drop_column('quote_requests', 'step_details')
    op.drop_column('quote_requests', 'progress_percentage')
    op.drop_column('quote_requests', 'current_step')
