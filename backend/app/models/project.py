from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    PLANEJAMENTO = "PLANEJAMENTO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"
    SUSPENSO = "SUSPENSO"


class Project(Base):
    """
    Projeto de Implantação
    Representa um projeto vinculado a um cliente (órgão público)
    As cotações são vinculadas a projetos
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Vinculação com cliente
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    # Dados do projeto
    nome = Column(String(300), nullable=False, index=True)
    codigo = Column(String(50), nullable=True, unique=True, index=True)  # Código interno do projeto
    descricao = Column(Text, nullable=True)

    # Contrato/Licitação
    numero_contrato = Column(String(100), nullable=True)
    numero_processo = Column(String(100), nullable=True)
    modalidade_licitacao = Column(String(100), nullable=True)  # Pregão, Concorrência, etc.

    # Datas
    data_inicio = Column(DateTime(timezone=True), nullable=True)
    data_previsao_fim = Column(DateTime(timezone=True), nullable=True)
    data_fim = Column(DateTime(timezone=True), nullable=True)

    # Valores
    valor_contrato = Column(Numeric(15, 2), nullable=True)

    # Status
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.PLANEJAMENTO)

    # Responsáveis
    responsavel_tecnico = Column(String(200), nullable=True)
    responsavel_cliente = Column(String(200), nullable=True)

    # Observações
    observacoes = Column(Text, nullable=True)

    # Módulos habilitados
    is_revaluation = Column(Boolean, default=True)  # Projeto de reavaliação
    is_inventory = Column(Boolean, default=False)   # Projeto de inventário

    # Configurações de inventário
    inventory_config = Column(JSONB, default={})
    # Estrutura do inventory_config:
    # {
    #   "require_photo": false,
    #   "photo_quality": "medium",
    #   "require_geolocation": true,
    #   "geofence_radius": 100,
    #   "block_outside_geofence": false,
    #   "allow_manual_entry": true,
    #   "allow_camera_barcode": true,
    #   "allow_unregistered_assets": true,
    #   "sync_mode": "batch",
    #   "auto_sync_on_complete": true
    # }

    # Sistema externo vinculado (para inventário)
    external_system_id = Column(Integer, ForeignKey("external_systems.id"), nullable=True)

    # Relacionamentos
    client = relationship("Client", back_populates="projetos")
    cotacoes = relationship("QuoteRequest", back_populates="project")
    config_versions = relationship("ProjectConfigVersion", back_populates="project", order_by="desc(ProjectConfigVersion.versao)")
    external_system = relationship("ExternalSystem")
    inventory_sessions = relationship("InventorySession", back_populates="project", cascade="all, delete-orphan")
