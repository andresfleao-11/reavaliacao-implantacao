"""add financial tables

Revision ID: 010
Revises: 009
Create Date: 2025-12-12

Adiciona:
- Tabela api_cost_config para configuração de custos das APIs
- Tabela financial_transactions para registro de transações
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela de configuração de custos de APIs
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_cost_config (
            id SERIAL PRIMARY KEY,
            api_name VARCHAR(50) NOT NULL,
            config_type VARCHAR(50) NOT NULL,
            start_date TIMESTAMP WITH TIME ZONE NOT NULL,
            end_date TIMESTAMP WITH TIME ZONE,
            total_calls INTEGER,
            total_cost_brl DECIMAL(10, 2),
            cost_per_call_brl DECIMAL(10, 6),
            cost_per_token_brl DECIMAL(10, 8),
            model_name VARCHAR(100),
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT unique_active_config UNIQUE (api_name, config_type, is_active)
        );
    """)

    # Criar tabela de transações financeiras
    op.execute("""
        CREATE TABLE IF NOT EXISTS financial_transactions (
            id SERIAL PRIMARY KEY,
            transaction_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            api_name VARCHAR(50) NOT NULL,
            quote_id INTEGER REFERENCES quote_requests(id) ON DELETE CASCADE,
            client_name VARCHAR(255),
            project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
            project_name VARCHAR(255),
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            user_name VARCHAR(255),
            description TEXT,
            quantity INTEGER,
            unit_cost_brl DECIMAL(10, 8),
            total_cost_brl DECIMAL(10, 2) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Criar índices
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_cost_config_id ON api_cost_config (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_cost_config_api_name ON api_cost_config (api_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_cost_config_is_active ON api_cost_config (is_active);")

    op.execute("CREATE INDEX IF NOT EXISTS ix_financial_transactions_id ON financial_transactions (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_financial_transactions_date ON financial_transactions (transaction_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_financial_transactions_api ON financial_transactions (api_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_financial_transactions_project ON financial_transactions (project_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_financial_transactions_quote ON financial_transactions (quote_id);")


def downgrade():
    op.drop_table('financial_transactions')
    op.drop_table('api_cost_config')
