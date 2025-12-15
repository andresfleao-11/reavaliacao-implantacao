"""Add variacao_percentual to quote_requests

Revision ID: 014_add_variacao_percentual
Revises: 013_add_integration_logs
Create Date: 2025-12-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade():
    # Add variacao_percentual column to quote_requests
    op.add_column('quote_requests', sa.Column('variacao_percentual', sa.Numeric(8, 4), nullable=True))


def downgrade():
    op.drop_column('quote_requests', 'variacao_percentual')
