"""Add RFID tables for middleware integration

Revision ID: 026_add_rfid_tables
Revises: 025_add_api_fipe_extraction_method
Create Date: 2024-12-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Criar tabela de lotes de leitura RFID
    op.create_table(
        'rfid_tag_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.String(100), nullable=False),
        sa.Column('device_id', sa.String(100), nullable=False),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('tag_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rfid_tag_batches_id', 'rfid_tag_batches', ['id'])
    op.create_index('ix_rfid_tag_batches_batch_id', 'rfid_tag_batches', ['batch_id'], unique=True)
    op.create_index('ix_rfid_tag_batches_device_id', 'rfid_tag_batches', ['device_id'])
    op.create_index('ix_rfid_tag_batches_project_id', 'rfid_tag_batches', ['project_id'])
    op.create_index('ix_rfid_tag_batches_created_at', 'rfid_tag_batches', ['created_at'])

    # Criar tabela de tags RFID
    op.create_table(
        'rfid_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('epc', sa.String(100), nullable=False),
        sa.Column('rssi', sa.String(20), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=True),
        sa.Column('matched', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['rfid_tag_batches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rfid_tags_id', 'rfid_tags', ['id'])
    op.create_index('ix_rfid_tags_batch_id', 'rfid_tags', ['batch_id'])
    op.create_index('ix_rfid_tags_epc', 'rfid_tags', ['epc'])
    op.create_index('ix_rfid_tags_item_id', 'rfid_tags', ['item_id'])
    op.create_index('ix_rfid_tags_epc_batch', 'rfid_tags', ['epc', 'batch_id'])


def downgrade() -> None:
    op.drop_table('rfid_tags')
    op.drop_table('rfid_tag_batches')
