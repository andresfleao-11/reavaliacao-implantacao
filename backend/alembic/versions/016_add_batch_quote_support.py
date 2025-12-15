"""add batch quote support

Revision ID: 016
Revises: add_check_constraints
Create Date: 2025-12-14 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '016'
down_revision: Union[str, None] = 'add_check_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add new values to quoteinputtype enum
    op.execute("ALTER TYPE quoteinputtype ADD VALUE IF NOT EXISTS 'TEXT_BATCH'")
    op.execute("ALTER TYPE quoteinputtype ADD VALUE IF NOT EXISTS 'IMAGE_BATCH'")
    op.execute("ALTER TYPE quoteinputtype ADD VALUE IF NOT EXISTS 'FILE_BATCH'")

    # 2. Add AWAITING_REVIEW to quotestatus enum
    op.execute("ALTER TYPE quotestatus ADD VALUE IF NOT EXISTS 'AWAITING_REVIEW'")

    # 3. Create batchjobstatus enum (use raw SQL with IF NOT EXISTS)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'batchjobstatus') THEN
                CREATE TYPE batchjobstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'ERROR', 'CANCELLED');
            END IF;
        END
        $$;
    """)

    # 4. Create batch_quote_jobs table if not exists
    result = conn.execute(sa.text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'batch_quote_jobs')"))
    table_exists = result.scalar()

    if not table_exists:
        op.execute("""
            CREATE TABLE batch_quote_jobs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE,
                status batchjobstatus NOT NULL DEFAULT 'PENDING',
                input_type VARCHAR(50) NOT NULL,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                config_version_id INTEGER REFERENCES project_config_versions(id) ON DELETE SET NULL,
                local VARCHAR(200),
                pesquisador VARCHAR(200),
                total_items INTEGER NOT NULL DEFAULT 0,
                completed_items INTEGER NOT NULL DEFAULT 0,
                failed_items INTEGER NOT NULL DEFAULT 0,
                original_input_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
                original_input_text TEXT,
                celery_task_id VARCHAR(255),
                last_processed_index INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            )
        """)

        # Create indexes for batch_quote_jobs
        op.create_index('ix_batch_quote_jobs_id', 'batch_quote_jobs', ['id'])
        op.create_index('ix_batch_quote_jobs_project_id', 'batch_quote_jobs', ['project_id'])
        op.create_index('ix_batch_quote_jobs_celery_task_id', 'batch_quote_jobs', ['celery_task_id'])
        op.create_index('ix_batch_quote_jobs_status', 'batch_quote_jobs', ['status'])
        op.create_index('ix_batch_quote_jobs_created_at', 'batch_quote_jobs', ['created_at'])

    # 5. Add new columns to quote_requests if they don't exist
    # Check batch_job_id column
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'batch_job_id'
        )
    """))
    if not result.scalar():
        op.add_column('quote_requests', sa.Column('batch_job_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_quote_requests_batch_job_id',
            'quote_requests',
            'batch_quote_jobs',
            ['batch_job_id'],
            ['id'],
            ondelete='SET NULL'
        )
        op.create_index('ix_quote_requests_batch_job_id', 'quote_requests', ['batch_job_id'])

    # Check batch_index column
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'batch_index'
        )
    """))
    if not result.scalar():
        op.add_column('quote_requests', sa.Column('batch_index', sa.Integer(), nullable=True))

    # Check google_shopping_response_json column
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'google_shopping_response_json'
        )
    """))
    if not result.scalar():
        op.add_column('quote_requests', sa.Column('google_shopping_response_json', sa.JSON(), nullable=True))

    # Check shopping_response_saved_at column
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'shopping_response_saved_at'
        )
    """))
    if not result.scalar():
        op.add_column('quote_requests', sa.Column('shopping_response_saved_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    # Check and remove columns from quote_requests
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'batch_job_id'
        )
    """))
    if result.scalar():
        op.drop_index('ix_quote_requests_batch_job_id', table_name='quote_requests')
        op.drop_constraint('fk_quote_requests_batch_job_id', 'quote_requests', type_='foreignkey')
        op.drop_column('quote_requests', 'batch_job_id')

    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'shopping_response_saved_at'
        )
    """))
    if result.scalar():
        op.drop_column('quote_requests', 'shopping_response_saved_at')

    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'google_shopping_response_json'
        )
    """))
    if result.scalar():
        op.drop_column('quote_requests', 'google_shopping_response_json')

    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'quote_requests' AND column_name = 'batch_index'
        )
    """))
    if result.scalar():
        op.drop_column('quote_requests', 'batch_index')

    # Drop batch_quote_jobs table if exists
    result = conn.execute(sa.text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'batch_quote_jobs')"))
    if result.scalar():
        op.drop_index('ix_batch_quote_jobs_created_at', table_name='batch_quote_jobs')
        op.drop_index('ix_batch_quote_jobs_status', table_name='batch_quote_jobs')
        op.drop_index('ix_batch_quote_jobs_celery_task_id', table_name='batch_quote_jobs')
        op.drop_index('ix_batch_quote_jobs_project_id', table_name='batch_quote_jobs')
        op.drop_index('ix_batch_quote_jobs_id', table_name='batch_quote_jobs')
        op.drop_table('batch_quote_jobs')

    # Drop batchjobstatus enum if exists
    op.execute("""
        DO $$
        BEGIN
            DROP TYPE IF EXISTS batchjobstatus;
        END
        $$;
    """)

    # Note: Cannot easily remove enum values in PostgreSQL
    # The new enum values (TEXT_BATCH, IMAGE_BATCH, FILE_BATCH, AWAITING_REVIEW)
    # will remain in the database but won't cause issues
