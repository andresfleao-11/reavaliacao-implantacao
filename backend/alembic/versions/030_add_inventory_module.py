"""Add inventory module tables

Revision ID: 030_add_inventory_module
Revises: 029_add_checkpoint_resume_fields
Create Date: 2024-12-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================
    # TABELA DE SISTEMAS EXTERNOS (Integração ASI e outros)
    # =====================================================
    op.create_table(
        'external_systems',
        sa.Column('id', sa.Integer(), nullable=False),

        # Identificação
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('system_type', sa.String(50), nullable=False),  # asi, sap, custom

        # Configuração de conexão
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('context_path', sa.String(100), nullable=True),
        sa.Column('full_url', sa.String(500), nullable=True),

        # Autenticação
        sa.Column('auth_type', sa.String(30), nullable=False, server_default='basic'),
        sa.Column('auth_username', sa.String(100), nullable=True),
        sa.Column('auth_password_encrypted', sa.String(500), nullable=True),
        sa.Column('auth_token_encrypted', sa.String(1000), nullable=True),
        sa.Column('auth_header_name', sa.String(50), nullable=True),

        # Endpoints configuráveis
        sa.Column('endpoint_test', sa.String(200), server_default='/coletorweb/servicecoletor/atualizar'),
        sa.Column('endpoint_load_assets', sa.String(200), server_default='/coletorweb/storages/create'),
        sa.Column('endpoint_upload', sa.String(200), server_default='/coletorweb/levantamento/upload'),
        sa.Column('endpoint_download_ug', sa.String(200), server_default='/coletorweb/ug/carregar'),
        sa.Column('endpoint_download_ul', sa.String(200), server_default='/coletorweb/ul/carregar'),
        sa.Column('endpoint_download_ua', sa.String(200), server_default='/coletorweb/ua/carregar'),
        sa.Column('endpoint_download_assets', sa.String(200), server_default='/coletorweb/bem/carregar'),
        sa.Column('endpoint_download_characteristics', sa.String(200), server_default='/coletorweb/caracteristica/carregar'),
        sa.Column('endpoint_download_physical_status', sa.String(200), server_default='/coletorweb/situacaofisica/carregar'),

        # Configurações adicionais
        sa.Column('timeout_seconds', sa.Integer(), server_default='60'),
        sa.Column('retry_attempts', sa.Integer(), server_default='3'),
        sa.Column('double_json_encoding', sa.Boolean(), server_default='true'),

        # Status
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),  # Sistema padrão do sistema
        sa.Column('last_test_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_test_success', sa.Boolean(), nullable=True),
        sa.Column('last_test_message', sa.Text(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),

        # Metadados
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),

        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_external_systems_type', 'external_systems', ['system_type'])
    op.create_index('idx_external_systems_active', 'external_systems', ['is_active'])

    # =====================================================
    # DADOS MESTRES SINCRONIZADOS
    # =====================================================

    # Unidades Gestoras
    op.create_table(
        'inventory_master_ug',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('extra_data', postgresql.JSONB(), server_default='{}'),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_system_id', 'code', name='uq_ug_system_code')
    )
    op.create_index('idx_master_ug_system', 'inventory_master_ug', ['external_system_id'])
    op.create_index('idx_master_ug_code', 'inventory_master_ug', ['code'])

    # Unidades Locais
    op.create_table(
        'inventory_master_ul',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ug_id', sa.Integer(), sa.ForeignKey('inventory_master_ug.id', ondelete='CASCADE'), nullable=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('radius_meters', sa.Integer(), server_default='100'),
        sa.Column('extra_data', postgresql.JSONB(), server_default='{}'),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_system_id', 'code', name='uq_ul_system_code')
    )
    op.create_index('idx_master_ul_system', 'inventory_master_ul', ['external_system_id'])
    op.create_index('idx_master_ul_ug', 'inventory_master_ul', ['ug_id'])

    # Unidades Administrativas
    op.create_table(
        'inventory_master_ua',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ul_id', sa.Integer(), sa.ForeignKey('inventory_master_ul.id', ondelete='CASCADE'), nullable=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('extra_data', postgresql.JSONB(), server_default='{}'),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_system_id', 'code', name='uq_ua_system_code')
    )

    # Situações Físicas
    op.create_table(
        'inventory_master_physical_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_system_id', 'code', name='uq_physical_status_system_code')
    )

    # Características de Bens
    op.create_table(
        'inventory_master_characteristics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('type', sa.String(30), nullable=True),  # text, number, date, list
        sa.Column('required', sa.Boolean(), server_default='false'),
        sa.Column('options', postgresql.JSONB(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_system_id', 'code', name='uq_characteristics_system_code')
    )

    # Log de sincronização de dados mestres
    op.create_table(
        'inventory_master_sync_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sync_type', sa.String(30), nullable=False),  # ug, ul, ua, characteristics, etc.
        sa.Column('status', sa.String(20), nullable=False),  # running, success, partial, failed
        sa.Column('items_received', sa.Integer(), server_default='0'),
        sa.Column('items_created', sa.Integer(), server_default='0'),
        sa.Column('items_updated', sa.Integer(), server_default='0'),
        sa.Column('items_failed', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sync_log_system', 'inventory_master_sync_log', ['external_system_id'])
    op.create_index('idx_sync_log_type', 'inventory_master_sync_log', ['sync_type'])

    # =====================================================
    # ALTERAÇÕES NA TABELA DE PROJETOS
    # =====================================================
    op.add_column('projects', sa.Column('is_inventory', sa.Boolean(), server_default='false'))
    op.add_column('projects', sa.Column('is_revaluation', sa.Boolean(), server_default='true'))
    op.add_column('projects', sa.Column('inventory_config', postgresql.JSONB(), server_default='{}'))
    op.add_column('projects', sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id'), nullable=True))

    # =====================================================
    # SESSÕES DE INVENTÁRIO
    # =====================================================
    op.create_table(
        'inventory_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_system_id', sa.Integer(), sa.ForeignKey('external_systems.id'), nullable=True),

        # Identificadores
        sa.Column('code', sa.String(50), nullable=False, unique=True),
        sa.Column('external_id', sa.String(100), nullable=True),

        # Localização hierárquica
        sa.Column('ug_id', sa.Integer(), sa.ForeignKey('inventory_master_ug.id'), nullable=True),
        sa.Column('ug_code', sa.String(50), nullable=True),
        sa.Column('ug_name', sa.String(200), nullable=True),
        sa.Column('ul_id', sa.Integer(), sa.ForeignKey('inventory_master_ul.id'), nullable=True),
        sa.Column('ul_code', sa.String(50), nullable=True),
        sa.Column('ul_name', sa.String(200), nullable=True),
        sa.Column('ua_id', sa.Integer(), sa.ForeignKey('inventory_master_ua.id'), nullable=True),
        sa.Column('ua_code', sa.String(50), nullable=True),
        sa.Column('ua_name', sa.String(200), nullable=True),

        # Geolocalização da UL
        sa.Column('ul_latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('ul_longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('ul_radius_meters', sa.Integer(), server_default='100'),

        # Responsável
        sa.Column('responsible_name', sa.String(200), nullable=True),
        sa.Column('responsible_registration', sa.String(50), nullable=True),

        # Status
        sa.Column('status', sa.String(30), server_default='draft'),  # draft, in_progress, completed, synced
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),

        # Estatísticas
        sa.Column('total_expected', sa.Integer(), server_default='0'),
        sa.Column('total_found', sa.Integer(), server_default='0'),
        sa.Column('total_not_found', sa.Integer(), server_default='0'),
        sa.Column('total_unregistered', sa.Integer(), server_default='0'),
        sa.Column('total_written_off', sa.Integer(), server_default='0'),

        # Metadados
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),

        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_inventory_sessions_project', 'inventory_sessions', ['project_id'])
    op.create_index('idx_inventory_sessions_status', 'inventory_sessions', ['status'])
    op.create_index('idx_inventory_sessions_code', 'inventory_sessions', ['code'])

    # =====================================================
    # BENS ESPERADOS (CARGA)
    # =====================================================
    op.create_table(
        'inventory_expected_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('inventory_sessions.id', ondelete='CASCADE'), nullable=False),

        # Identificadores do bem
        sa.Column('asset_code', sa.String(50), nullable=False),
        sa.Column('asset_sequence', sa.String(20), nullable=True),
        sa.Column('rfid_code', sa.String(100), nullable=True),
        sa.Column('barcode', sa.String(100), nullable=True),

        # Descrição
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),

        # Localização esperada
        sa.Column('expected_ul_code', sa.String(50), nullable=True),
        sa.Column('expected_ua_code', sa.String(50), nullable=True),

        # Situação no sistema externo
        sa.Column('is_written_off', sa.Boolean(), server_default='false'),

        # Status de processamento
        sa.Column('processed', sa.Boolean(), server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),

        # Dados extras do sistema externo
        sa.Column('extra_data', postgresql.JSONB(), server_default='{}'),

        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_expected_assets_session', 'inventory_expected_assets', ['session_id'])
    op.create_index('idx_expected_assets_code', 'inventory_expected_assets', ['asset_code'])
    op.create_index('idx_expected_assets_rfid', 'inventory_expected_assets', ['rfid_code'])
    op.create_index('idx_expected_assets_barcode', 'inventory_expected_assets', ['barcode'])
    op.create_unique_constraint('uq_expected_asset_session_code', 'inventory_expected_assets', ['session_id', 'asset_code'])

    # =====================================================
    # BENS LIDOS
    # =====================================================
    op.create_table(
        'inventory_read_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('inventory_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expected_asset_id', sa.Integer(), sa.ForeignKey('inventory_expected_assets.id', ondelete='SET NULL'), nullable=True),

        # Identificadores
        sa.Column('asset_code', sa.String(50), nullable=True),
        sa.Column('rfid_code', sa.String(100), nullable=True),
        sa.Column('barcode', sa.String(100), nullable=True),

        # Método de leitura
        sa.Column('read_method', sa.String(20), nullable=False),  # rfid, barcode, camera, manual
        sa.Column('device_model', sa.String(50), nullable=True),

        # Categorização
        sa.Column('category', sa.String(30), nullable=False),  # found, not_found, unregistered, written_off

        # Situação física
        sa.Column('physical_condition', sa.String(30), nullable=True),  # good, damaged, needs_repair, unusable
        sa.Column('physical_condition_code', sa.String(20), nullable=True),  # Código do sistema externo

        # Geolocalização da leitura
        sa.Column('read_latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('read_longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('geolocation_valid', sa.Boolean(), nullable=True),

        # Foto do bem
        sa.Column('photo_file_id', sa.String(100), nullable=True),
        sa.Column('photo_path', sa.String(500), nullable=True),

        # Observações
        sa.Column('notes', sa.Text(), nullable=True),

        # Timestamp
        sa.Column('read_at', sa.DateTime(timezone=True), server_default=sa.func.now()),

        # Sincronização
        sa.Column('synced', sa.Boolean(), server_default='false'),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('external_status', sa.String(50), nullable=True),

        # Para modo offline
        sa.Column('local_id', sa.String(100), nullable=True),  # ID local gerado offline
        sa.Column('pending_sync', sa.Boolean(), server_default='false'),

        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_read_assets_session', 'inventory_read_assets', ['session_id'])
    op.create_index('idx_read_assets_category', 'inventory_read_assets', ['category'])
    op.create_index('idx_read_assets_expected', 'inventory_read_assets', ['expected_asset_id'])
    op.create_index('idx_read_assets_pending_sync', 'inventory_read_assets', ['pending_sync'])

    # =====================================================
    # LOG DE SINCRONIZAÇÃO DE SESSÕES
    # =====================================================
    op.create_table(
        'inventory_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('inventory_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sync_type', sa.String(20), nullable=False),  # download, upload
        sa.Column('status', sa.String(20), nullable=False),  # success, partial, failed
        sa.Column('items_sent', sa.Integer(), nullable=True),
        sa.Column('items_success', sa.Integer(), nullable=True),
        sa.Column('items_failed', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('response_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sync_logs_session', 'inventory_sync_logs', ['session_id'])


def downgrade() -> None:
    # Drop inventory sync logs
    op.drop_index('idx_sync_logs_session', table_name='inventory_sync_logs')
    op.drop_table('inventory_sync_logs')

    # Drop read assets
    op.drop_index('idx_read_assets_pending_sync', table_name='inventory_read_assets')
    op.drop_index('idx_read_assets_expected', table_name='inventory_read_assets')
    op.drop_index('idx_read_assets_category', table_name='inventory_read_assets')
    op.drop_index('idx_read_assets_session', table_name='inventory_read_assets')
    op.drop_table('inventory_read_assets')

    # Drop expected assets
    op.drop_constraint('uq_expected_asset_session_code', 'inventory_expected_assets', type_='unique')
    op.drop_index('idx_expected_assets_barcode', table_name='inventory_expected_assets')
    op.drop_index('idx_expected_assets_rfid', table_name='inventory_expected_assets')
    op.drop_index('idx_expected_assets_code', table_name='inventory_expected_assets')
    op.drop_index('idx_expected_assets_session', table_name='inventory_expected_assets')
    op.drop_table('inventory_expected_assets')

    # Drop inventory sessions
    op.drop_index('idx_inventory_sessions_code', table_name='inventory_sessions')
    op.drop_index('idx_inventory_sessions_status', table_name='inventory_sessions')
    op.drop_index('idx_inventory_sessions_project', table_name='inventory_sessions')
    op.drop_table('inventory_sessions')

    # Remove columns from projects
    op.drop_column('projects', 'external_system_id')
    op.drop_column('projects', 'inventory_config')
    op.drop_column('projects', 'is_revaluation')
    op.drop_column('projects', 'is_inventory')

    # Drop master sync log
    op.drop_index('idx_sync_log_type', table_name='inventory_master_sync_log')
    op.drop_index('idx_sync_log_system', table_name='inventory_master_sync_log')
    op.drop_table('inventory_master_sync_log')

    # Drop characteristics
    op.drop_table('inventory_master_characteristics')

    # Drop physical status
    op.drop_table('inventory_master_physical_status')

    # Drop UA
    op.drop_table('inventory_master_ua')

    # Drop UL
    op.drop_index('idx_master_ul_ug', table_name='inventory_master_ul')
    op.drop_index('idx_master_ul_system', table_name='inventory_master_ul')
    op.drop_table('inventory_master_ul')

    # Drop UG
    op.drop_index('idx_master_ug_code', table_name='inventory_master_ug')
    op.drop_index('idx_master_ug_system', table_name='inventory_master_ug')
    op.drop_table('inventory_master_ug')

    # Drop external systems
    op.drop_index('idx_external_systems_active', table_name='external_systems')
    op.drop_index('idx_external_systems_type', table_name='external_systems')
    op.drop_table('external_systems')
