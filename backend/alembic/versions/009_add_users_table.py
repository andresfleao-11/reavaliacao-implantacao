"""add_users_table

Revision ID: 009
Revises: 008
Create Date: 2025-12-11

Adiciona:
- Tabela users com campos: email, nome, senha, role (ADMIN/USER), ativo
- Cria usuário admin padrão
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Criar enum para roles (só se não existir)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE userrole AS ENUM ('ADMIN', 'USER');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Criar tabela users (só se não existir)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            nome VARCHAR(255) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            role userrole NOT NULL DEFAULT 'USER',
            ativo BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)

    # Criar índices se não existirem
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);")

    # Criar usuário admin padrão (senha: admin123) - só se não existir
    # Hash gerado para "admin123" usando bcrypt
    hashed_password = "$2b$12$FPUHX1R0k2WlmvFy6.d6QO4JFcHA4lWXqVJdMsvjpOUhf1Kz2vVi."
    op.execute(f"""
        INSERT INTO users (email, nome, hashed_password, role, ativo)
        SELECT 'admin@sistema.com', 'Administrador', '{hashed_password}', 'ADMIN', true
        WHERE NOT EXISTS (
            SELECT 1 FROM users WHERE email = 'admin@sistema.com'
        );
    """)


def downgrade():
    op.drop_table('users')
    op.execute("DROP TYPE userrole")
