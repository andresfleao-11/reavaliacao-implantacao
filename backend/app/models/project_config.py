from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ProjectConfigVersion(Base):
    """
    Versão das Configurações do Projeto
    Cada alteração nas configurações cria uma nova versão
    As cotações fazem referência a uma versão específica
    """
    __tablename__ = "project_config_versions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Vinculação com projeto
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    # Número da versão (auto-incrementado por projeto)
    versao = Column(Integer, nullable=False, default=1)

    # Descrição da alteração (changelog)
    descricao_alteracao = Column(Text, nullable=True)

    # Usuário que criou a versão
    criado_por = Column(String(200), nullable=True)

    # Se é a versão atual/ativa
    ativo = Column(Boolean, default=True)

    # ========== PARÂMETROS DE COTAÇÃO ==========
    # Número de cotações por pesquisa
    numero_cotacoes_por_pesquisa = Column(Integer, nullable=True)
    # Máximo de cotações armazenadas por item
    max_cotacoes_armazenadas_por_item = Column(Integer, nullable=True)
    # Variação máxima permitida (%) - Fórmula: (MAX/MIN - 1) * 100
    variacao_maxima_percent = Column(Numeric(5, 2), nullable=True)
    # Pesquisador padrão
    pesquisador_padrao = Column(String(200), nullable=True)
    # Local padrão
    local_padrao = Column(String(200), nullable=True)

    # ========== BANCO DE PREÇO DE VEÍCULOS ==========
    # Vigência de cotação em meses (padrão: 6 meses)
    vigencia_cotacao_veiculos = Column(Integer, nullable=True, default=6)

    # ========== PARÂMETROS DE BUSCA ==========
    # Configurações da SerpAPI
    serpapi_location = Column(String(200), nullable=True)
    serpapi_gl = Column(String(10), default="br")
    serpapi_hl = Column(String(10), default="pt")
    serpapi_num_results = Column(Integer, default=10)

    # Outras configurações de busca
    search_timeout = Column(Integer, default=30)
    max_sources = Column(Integer, default=10)

    # ========== VALIDAÇÃO DE PREÇOS ==========
    # Habilitar/desabilitar validação de PRICE_MISMATCH (preço Google vs Site)
    # Se desabilitado, não invalida o produto por diferença de preço, mas ainda registra no log
    enable_price_mismatch_validation = Column(Boolean, default=True)

    # ========== VALIDAÇÃO DE ESPECIFICAÇÕES (v2.0) ==========
    # Habilitar extração de especificações das páginas de produto
    enable_spec_extraction = Column(Boolean, default=False)
    # Habilitar validação query vs specs (tipo, material, dimensões)
    enable_spec_validation = Column(Boolean, default=False)
    # Tolerância para dimensões (0.20 = 20%)
    spec_dimension_tolerance = Column(Numeric(5, 2), default=0.20)

    # ========== CÁLCULO DE METRO LINEAR (v2.0) ==========
    # Habilitar fluxo de metro linear para bens com dimensões especiais
    enable_linear_meter = Column(Boolean, default=False)
    # Mínimo de produtos para cálculo de metro linear
    linear_meter_min_products = Column(Integer, default=2)

    # ========== BANCO DE PREÇOS ==========
    # JSON com lista de itens do banco de preços
    # Formato: [{"codigo": "X", "material": "Y", "caracteristicas": "Z", "vl_mercado": 1000.00, "update_mode": "MARKET"}]
    banco_precos_json = Column(JSON, nullable=True)

    # ========== FATOR DE REAVALIAÇÃO ==========
    # Mapa de Estado de Conservação (EC)
    # Formato: {"OTIMO": 1.0, "BOM": 0.8, "REGULAR": 0.6, "RUIM": 0.4}
    ec_map_json = Column(JSON, nullable=True)

    # Mapa de Período de Utilização (PU)
    # Formato: {"0-2": 1.0, "2-5": 0.8, "5-10": 0.6, ">10": 0.4}
    pu_map_json = Column(JSON, nullable=True)

    # Mapa de Vida Útil Futura (VUF)
    # Formato: {">5": 1.0, "3-5": 0.8, "1-3": 0.6, "<1": 0.4}
    vuf_map_json = Column(JSON, nullable=True)

    # Pesos para cálculo do fator
    # Formato: {"ec": 0.4, "pu": 0.3, "vuf": 0.3}
    weights_json = Column(JSON, nullable=True)

    # Relacionamentos
    project = relationship("Project", back_populates="config_versions")
    cotacoes = relationship("QuoteRequest", back_populates="config_version")


class ProjectBankPrice(Base):
    """
    Item do Banco de Preços do Projeto
    Cada projeto pode ter seu próprio banco de preços
    """
    __tablename__ = "project_bank_prices"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Vinculação com versão da configuração
    config_version_id = Column(Integer, ForeignKey("project_config_versions.id"), nullable=False, index=True)

    # Dados do item
    codigo = Column(String(100), nullable=False, index=True)
    material = Column(String(500), nullable=False)
    caracteristicas = Column(Text, nullable=True)
    vl_mercado = Column(Numeric(12, 2), nullable=True)

    # Modo de atualização: MARKET (busca mercado), IPCA (corrige por índice), MANUAL, SKIP
    update_mode = Column(String(20), default="MARKET")

    # Relacionamento
    config_version = relationship("ProjectConfigVersion")
