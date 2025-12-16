"""add has_screenshot to vehicle_price_bank

Revision ID: 022
Revises: 021
Create Date: 2024-12-16 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '022'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add has_screenshot column (computed based on screenshot_path)
    op.add_column('vehicle_price_bank', sa.Column('has_screenshot', sa.Boolean(), nullable=True, server_default='false'))

    # Update existing records based on screenshot_path
    op.execute("""
        UPDATE vehicle_price_bank
        SET has_screenshot = (screenshot_path IS NOT NULL AND screenshot_path != '')
    """)


def downgrade() -> None:
    op.drop_column('vehicle_price_bank', 'has_screenshot')
