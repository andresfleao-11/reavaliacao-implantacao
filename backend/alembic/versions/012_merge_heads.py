"""merge heads

Revision ID: 012
Revises: 011, 915122f32fed
Create Date: 2025-12-12 14:03:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012'
down_revision = ('011', '915122f32fed')
branch_labels = None
depends_on = None


def upgrade():
    # Merge migration - no changes needed
    pass


def downgrade():
    # Merge migration - no changes needed
    pass
