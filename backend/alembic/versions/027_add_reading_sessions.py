"""Add reading sessions tables

Revision ID: 027
Revises: 026
Create Date: 2025-01-01

"""
from alembic import op
import sqlalchemy as sa


revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela de sessões de leitura
    op.create_table(
        'reading_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reading_type', sa.Enum('RFID', 'BARCODE', name='readingtype'), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'COMPLETED', 'CANCELLED', 'EXPIRED', name='sessionstatus'),
                  server_default='ACTIVE', nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), server_default='300', nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reading_sessions_id'), 'reading_sessions', ['id'], unique=False)
    op.create_index('ix_reading_sessions_status', 'reading_sessions', ['status'], unique=False)
    op.create_index('ix_reading_sessions_user_id', 'reading_sessions', ['user_id'], unique=False)

    # Criar tabela de leituras individuais
    op.create_table(
        'session_readings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=255), nullable=False),
        sa.Column('rssi', sa.String(length=20), nullable=True),
        sa.Column('device_id', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['reading_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_readings_id'), 'session_readings', ['id'], unique=False)
    op.create_index('ix_session_readings_session_id', 'session_readings', ['session_id'], unique=False)
    op.create_index('ix_session_readings_code', 'session_readings', ['code'], unique=False)


def downgrade():
    op.drop_index('ix_session_readings_code', table_name='session_readings')
    op.drop_index('ix_session_readings_session_id', table_name='session_readings')
    op.drop_index(op.f('ix_session_readings_id'), table_name='session_readings')
    op.drop_table('session_readings')

    op.drop_index('ix_reading_sessions_user_id', table_name='reading_sessions')
    op.drop_index('ix_reading_sessions_status', table_name='reading_sessions')
    op.drop_index(op.f('ix_reading_sessions_id'), table_name='reading_sessions')
    op.drop_table('reading_sessions')

    # Remove enums
    op.execute('DROP TYPE IF EXISTS sessionstatus')
    op.execute('DROP TYPE IF EXISTS readingtype')
