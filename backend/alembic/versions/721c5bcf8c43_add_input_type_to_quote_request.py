"""add_input_type_to_quote_request

Revision ID: 721c5bcf8c43
Revises: 71d6136f9631
Create Date: 2025-12-14 04:04:41.156680

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '721c5bcf8c43'
down_revision: Union[str, None] = '71d6136f9631'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type first
    quoteinputtype = sa.Enum('TEXT', 'IMAGE', 'GOOGLE_LENS', name='quoteinputtype')
    quoteinputtype.create(op.get_bind(), checkfirst=True)

    # Add the column with default value TEXT
    op.add_column('quote_requests', sa.Column('input_type', quoteinputtype, nullable=True, server_default='TEXT'))

    # Update existing rows - determine type based on existing data
    # If has input images -> IMAGE, else -> TEXT
    op.execute("""
        UPDATE quote_requests
        SET input_type = CASE
            WHEN id IN (SELECT DISTINCT quote_request_id FROM files WHERE type = 'INPUT_IMAGE') THEN 'IMAGE'::quoteinputtype
            ELSE 'TEXT'::quoteinputtype
        END
        WHERE input_type IS NULL
    """)


def downgrade() -> None:
    op.drop_column('quote_requests', 'input_type')
    # Drop the enum type
    sa.Enum(name='quoteinputtype').drop(op.get_bind(), checkfirst=True)
