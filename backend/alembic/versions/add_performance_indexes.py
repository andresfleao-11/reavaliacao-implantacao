"""add performance indexes

Revision ID: add_performance_indexes
Revises:
Create Date: 2024-12-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_performance_indexes'
down_revision = '721c5bcf8c43'
branch_labels = None
depends_on = None


def upgrade():
    """Adiciona índices para melhorar performance"""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    def create_index_if_not_exists(index_name, table_name, columns, unique=False):
        """Cria índice apenas se não existir"""
        existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns, unique=unique)

    # Índices em quote_requests
    create_index_if_not_exists(
        'ix_quote_requests_created_at',
        'quote_requests',
        ['created_at']
    )
    create_index_if_not_exists(
        'ix_quote_requests_status',
        'quote_requests',
        ['status']
    )
    create_index_if_not_exists(
        'ix_quote_requests_project_status',
        'quote_requests',
        ['project_id', 'status']
    )
    create_index_if_not_exists(
        'ix_quote_requests_project_created',
        'quote_requests',
        ['project_id', 'created_at']
    )

    # Índices em quote_sources
    create_index_if_not_exists(
        'ix_quote_sources_quote_request_id',
        'quote_sources',
        ['quote_request_id']
    )
    create_index_if_not_exists(
        'ix_quote_sources_is_accepted',
        'quote_sources',
        ['is_accepted']
    )

    # Índices em files
    create_index_if_not_exists(
        'ix_files_quote_request_id',
        'files',
        ['quote_request_id']
    )
    create_index_if_not_exists(
        'ix_files_type',
        'files',
        ['type']
    )

    # Índices em integration_logs
    create_index_if_not_exists(
        'ix_integration_logs_quote_request_id',
        'integration_logs',
        ['quote_request_id']
    )
    create_index_if_not_exists(
        'ix_integration_logs_created_at',
        'integration_logs',
        ['created_at']
    )

    # Índices em users
    create_index_if_not_exists(
        'ix_users_email',
        'users',
        ['email'],
        unique=True
    )
    create_index_if_not_exists(
        'ix_users_role',
        'users',
        ['role']
    )

    # Índices em projects
    create_index_if_not_exists(
        'ix_projects_client_id',
        'projects',
        ['client_id']
    )

    # Índices em financial_transactions
    create_index_if_not_exists(
        'ix_financial_transactions_quote_id',
        'financial_transactions',
        ['quote_id']
    )
    create_index_if_not_exists(
        'ix_financial_transactions_created_at',
        'financial_transactions',
        ['created_at']
    )


def downgrade():
    """Remove os índices adicionados"""

    # Remover índices de quote_requests
    op.drop_index('ix_quote_requests_created_at', table_name='quote_requests')
    op.drop_index('ix_quote_requests_status', table_name='quote_requests')
    op.drop_index('ix_quote_requests_project_status', table_name='quote_requests')
    op.drop_index('ix_quote_requests_project_created', table_name='quote_requests')

    # Remover índices de quote_sources
    op.drop_index('ix_quote_sources_quote_request_id', table_name='quote_sources')
    op.drop_index('ix_quote_sources_is_accepted', table_name='quote_sources')

    # Remover índices de files
    op.drop_index('ix_files_quote_request_id', table_name='files')
    op.drop_index('ix_files_type', table_name='files')

    # Remover índices de integration_logs
    op.drop_index('ix_integration_logs_quote_request_id', table_name='integration_logs')
    op.drop_index('ix_integration_logs_created_at', table_name='integration_logs')

    # Remover índices de users
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_role', table_name='users')

    # Remover índices de projects
    op.drop_index('ix_projects_client_id', table_name='projects')

    # Remover índices de financial_transactions
    op.drop_index('ix_financial_transactions_quote_id', table_name='financial_transactions')
    op.drop_index('ix_financial_transactions_created_at', table_name='financial_transactions')
