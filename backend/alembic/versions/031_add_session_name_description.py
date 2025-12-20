"""Add name and description to inventory_sessions

Revision ID: 031
Revises: 030
Create Date: 2024-12-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add name and description columns to inventory_sessions
    op.add_column('inventory_sessions', sa.Column('name', sa.String(200), nullable=True))
    op.add_column('inventory_sessions', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('inventory_sessions', sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('inventory_sessions', sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=True))

    # Add created_by_id column (correcting name from created_by)
    # Note: created_by already exists, just rename in model


def downgrade() -> None:
    op.drop_column('inventory_sessions', 'scheduled_end')
    op.drop_column('inventory_sessions', 'scheduled_start')
    op.drop_column('inventory_sessions', 'description')
    op.drop_column('inventory_sessions', 'name')
