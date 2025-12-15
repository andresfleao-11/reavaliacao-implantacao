"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-12-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('quote_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('PROCESSING', 'DONE', 'ERROR', name='quotestatus'), nullable=True),
        sa.Column('input_text', sa.Text(), nullable=True),
        sa.Column('codigo_item', sa.String(length=100), nullable=True),
        sa.Column('claude_payload_json', sa.JSON(), nullable=True),
        sa.Column('search_query_final', sa.Text(), nullable=True),
        sa.Column('local', sa.String(length=200), nullable=True),
        sa.Column('pesquisador', sa.String(length=200), nullable=True),
        sa.Column('valor_medio', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('valor_minimo', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('valor_maximo', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_requests_codigo_item'), 'quote_requests', ['codigo_item'], unique=False)
    op.create_index(op.f('ix_quote_requests_id'), 'quote_requests', ['id'], unique=False)

    op.create_table('files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('INPUT_IMAGE', 'SCREENSHOT', 'PDF', name='filetype'), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('quote_request_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['quote_request_id'], ['quote_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_files_id'), 'files', ['id'], unique=False)
    op.create_index(op.f('ix_files_sha256'), 'files', ['sha256'], unique=False)

    op.create_table('quote_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_request_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('page_title', sa.Text(), nullable=True),
        sa.Column('price_value', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('extraction_method', sa.Enum('JSONLD', 'META', 'DOM', 'LLM', name='extractionmethod'), nullable=True),
        sa.Column('screenshot_file_id', sa.Integer(), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_outlier', sa.Boolean(), nullable=True),
        sa.Column('is_accepted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['quote_request_id'], ['quote_requests.id'], ),
        sa.ForeignKeyConstraint(['screenshot_file_id'], ['files.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_sources_domain'), 'quote_sources', ['domain'], unique=False)
    op.create_index(op.f('ix_quote_sources_id'), 'quote_sources', ['id'], unique=False)
    op.create_index(op.f('ix_quote_sources_quote_request_id'), 'quote_sources', ['quote_request_id'], unique=False)

    op.create_table('generated_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_request_id', sa.Integer(), nullable=False),
        sa.Column('pdf_file_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['pdf_file_id'], ['files.id'], ),
        sa.ForeignKeyConstraint(['quote_request_id'], ['quote_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generated_documents_id'), 'generated_documents', ['id'], unique=False)
    op.create_index(op.f('ix_generated_documents_quote_request_id'), 'generated_documents', ['quote_request_id'], unique=False)

    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value_json', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settings_id'), 'settings', ['id'], unique=False)
    op.create_index(op.f('ix_settings_key'), 'settings', ['key'], unique=True)

    op.create_table('bank_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=100), nullable=False),
        sa.Column('material', sa.String(length=500), nullable=False),
        sa.Column('caracteristicas', sa.Text(), nullable=True),
        sa.Column('vl_mercado', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('update_mode', sa.Enum('MARKET', 'IPCA', 'MANUAL', 'SKIP', name='updatemode'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bank_prices_codigo'), 'bank_prices', ['codigo'], unique=True)
    op.create_index(op.f('ix_bank_prices_id'), 'bank_prices', ['id'], unique=False)

    op.create_table('revaluation_params',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ec_map_json', sa.JSON(), nullable=False),
        sa.Column('pu_map_json', sa.JSON(), nullable=False),
        sa.Column('vuf_map_json', sa.JSON(), nullable=False),
        sa.Column('weights_json', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_revaluation_params_id'), 'revaluation_params', ['id'], unique=False)

    op.create_table('integration_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('settings_json', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_integration_settings_id'), 'integration_settings', ['id'], unique=False)
    op.create_index(op.f('ix_integration_settings_provider'), 'integration_settings', ['provider'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_integration_settings_provider'), table_name='integration_settings')
    op.drop_index(op.f('ix_integration_settings_id'), table_name='integration_settings')
    op.drop_table('integration_settings')

    op.drop_index(op.f('ix_revaluation_params_id'), table_name='revaluation_params')
    op.drop_table('revaluation_params')

    op.drop_index(op.f('ix_bank_prices_id'), table_name='bank_prices')
    op.drop_index(op.f('ix_bank_prices_codigo'), table_name='bank_prices')
    op.drop_table('bank_prices')

    op.drop_index(op.f('ix_settings_key'), table_name='settings')
    op.drop_index(op.f('ix_settings_id'), table_name='settings')
    op.drop_table('settings')

    op.drop_index(op.f('ix_generated_documents_quote_request_id'), table_name='generated_documents')
    op.drop_index(op.f('ix_generated_documents_id'), table_name='generated_documents')
    op.drop_table('generated_documents')

    op.drop_index(op.f('ix_quote_sources_quote_request_id'), table_name='quote_sources')
    op.drop_index(op.f('ix_quote_sources_id'), table_name='quote_sources')
    op.drop_index(op.f('ix_quote_sources_domain'), table_name='quote_sources')
    op.drop_table('quote_sources')

    op.drop_index(op.f('ix_files_sha256'), table_name='files')
    op.drop_index(op.f('ix_files_id'), table_name='files')
    op.drop_table('files')

    op.drop_index(op.f('ix_quote_requests_id'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_codigo_item'), table_name='quote_requests')
    op.drop_table('quote_requests')
