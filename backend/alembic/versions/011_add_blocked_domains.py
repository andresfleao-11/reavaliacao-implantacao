"""add blocked domains table

Revision ID: 011
Revises: 010
Create Date: 2025-12-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela de domínios bloqueados
    op.create_table(
        'blocked_domains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain')
    )

    # Índice para busca rápida
    op.create_index('idx_blocked_domains_domain', 'blocked_domains', ['domain'])

    # Inserir domínios padrão (migrar do código para banco)
    op.execute("""
        INSERT INTO blocked_domains (domain, display_name, reason) VALUES
        -- Marketplaces com proteção anti-bot forte
        ('mercadolivre.com.br', 'Mercado Livre', 'Proteção anti-bot forte'),
        ('mercadoshops.com.br', 'Mercado Shops', 'Proteção anti-bot forte'),
        ('amazon.com.br', 'Amazon Brasil', 'Proteção anti-bot forte'),
        ('amazon.com', 'Amazon', 'Proteção anti-bot forte'),
        ('aliexpress.com', 'AliExpress', 'Proteção anti-bot forte'),
        ('aliexpress.com.br', 'AliExpress Brasil', 'Proteção anti-bot forte'),
        ('shopee.com.br', 'Shopee', 'Proteção anti-bot forte'),
        ('shein.com', 'Shein', 'Proteção anti-bot forte'),
        ('shein.com.br', 'Shein Brasil', 'Proteção anti-bot forte'),
        ('wish.com', 'Wish', 'Proteção anti-bot forte'),
        ('temu.com', 'Temu', 'Proteção anti-bot forte'),
        -- Grandes varejistas com Cloudflare/anti-bot
        ('carrefour.com.br', 'Carrefour', 'Cloudflare/proteção anti-bot'),
        ('casasbahia.com.br', 'Casas Bahia', 'Cloudflare/proteção anti-bot'),
        ('pontofrio.com.br', 'Ponto Frio', 'Cloudflare/proteção anti-bot'),
        ('extra.com.br', 'Extra', 'Cloudflare/proteção anti-bot'),
        ('magazineluiza.com.br', 'Magazine Luiza', 'Cloudflare/proteção anti-bot'),
        ('magalu.com.br', 'Magalu', 'Cloudflare/proteção anti-bot'),
        ('americanas.com.br', 'Americanas', 'Cloudflare/proteção anti-bot'),
        ('submarino.com.br', 'Submarino', 'Cloudflare/proteção anti-bot'),
        ('shoptime.com.br', 'Shoptime', 'Cloudflare/proteção anti-bot')
    """)


def downgrade():
    op.drop_index('idx_blocked_domains_domain')
    op.drop_table('blocked_domains')
