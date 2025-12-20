"""
Models para Sistemas Externos e Dados Mestres de Inventário
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Boolean, Numeric, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class SystemType(str, enum.Enum):
    """Tipos de sistemas externos suportados"""
    ASI = "asi"
    SAP = "sap"
    CUSTOM = "custom"


class AuthType(str, enum.Enum):
    """Tipos de autenticação"""
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    NONE = "none"


class SyncStatus(str, enum.Enum):
    """Status de sincronização"""
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExternalSystem(Base):
    """
    Configuração de sistema externo para integração.
    Exemplo: ASI (Sistema de Patrimônio)
    """
    __tablename__ = "external_systems"

    id = Column(Integer, primary_key=True, index=True)

    # Identificação
    name = Column(String(100), nullable=False)
    system_type = Column(String(50), nullable=False, default=SystemType.ASI.value)

    # Configuração de conexão
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=True)
    context_path = Column(String(100), nullable=True)
    full_url = Column(String(500), nullable=True)

    # Autenticação
    auth_type = Column(String(30), nullable=False, default=AuthType.BASIC.value)
    auth_username = Column(String(100), nullable=True)
    auth_password_encrypted = Column(String(500), nullable=True)
    auth_token_encrypted = Column(String(1000), nullable=True)
    auth_header_name = Column(String(50), nullable=True)

    # Endpoints configuráveis
    endpoint_test = Column(String(200), default='/coletorweb/servicecoletor/atualizar')
    endpoint_load_assets = Column(String(200), default='/coletorweb/storages/create')
    endpoint_upload = Column(String(200), default='/coletorweb/levantamento/upload')
    endpoint_download_ug = Column(String(200), default='/coletorweb/ug/carregar')
    endpoint_download_ul = Column(String(200), default='/coletorweb/ul/carregar')
    endpoint_download_ua = Column(String(200), default='/coletorweb/ua/carregar')
    endpoint_download_assets = Column(String(200), default='/coletorweb/bem/carregar')
    endpoint_download_characteristics = Column(String(200), default='/coletorweb/caracteristica/carregar')
    endpoint_download_physical_status = Column(String(200), default='/coletorweb/situacaofisica/carregar')

    # Configurações adicionais
    timeout_seconds = Column(Integer, default=60)
    retry_attempts = Column(Integer, default=3)
    double_json_encoding = Column(Boolean, default=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    last_test_at = Column(DateTime(timezone=True), nullable=True)
    last_test_success = Column(Boolean, nullable=True)
    last_test_message = Column(Text, nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Metadados
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    ugs = relationship("InventoryMasterUG", back_populates="external_system", cascade="all, delete-orphan")
    uls = relationship("InventoryMasterUL", back_populates="external_system", cascade="all, delete-orphan")
    uas = relationship("InventoryMasterUA", back_populates="external_system", cascade="all, delete-orphan")
    physical_statuses = relationship("InventoryMasterPhysicalStatus", back_populates="external_system", cascade="all, delete-orphan")
    characteristics = relationship("InventoryMasterCharacteristic", back_populates="external_system", cascade="all, delete-orphan")
    sync_logs = relationship("InventoryMasterSyncLog", back_populates="external_system", cascade="all, delete-orphan")

    def build_full_url(self) -> str:
        """Monta a URL completa do sistema"""
        url = self.host.rstrip('/')
        if self.port:
            url += f":{self.port}"
        if self.context_path:
            url += '/' + self.context_path.strip('/')
        return url

    def get_endpoint_url(self, endpoint_name: str) -> str:
        """Retorna URL completa de um endpoint"""
        base = self.full_url or self.build_full_url()
        endpoint = getattr(self, f"endpoint_{endpoint_name}", None)
        if endpoint:
            return base + endpoint
        return base


class InventoryMasterUG(Base):
    """Unidade Gestora - sincronizada do sistema externo"""
    __tablename__ = "inventory_master_ug"

    id = Column(Integer, primary_key=True, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    extra_data = Column(JSONB, default={})
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    external_system = relationship("ExternalSystem", back_populates="ugs")
    uls = relationship("InventoryMasterUL", back_populates="ug", cascade="all, delete-orphan")


class InventoryMasterUL(Base):
    """Unidade Local - sincronizada do sistema externo"""
    __tablename__ = "inventory_master_ul"

    id = Column(Integer, primary_key=True, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id", ondelete="CASCADE"), nullable=False)
    ug_id = Column(Integer, ForeignKey("inventory_master_ug.id", ondelete="CASCADE"), nullable=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    radius_meters = Column(Integer, default=100)
    extra_data = Column(JSONB, default={})
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    external_system = relationship("ExternalSystem", back_populates="uls")
    ug = relationship("InventoryMasterUG", back_populates="uls")
    uas = relationship("InventoryMasterUA", back_populates="ul", cascade="all, delete-orphan")


class InventoryMasterUA(Base):
    """Unidade Administrativa - sincronizada do sistema externo"""
    __tablename__ = "inventory_master_ua"

    id = Column(Integer, primary_key=True, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id", ondelete="CASCADE"), nullable=False)
    ul_id = Column(Integer, ForeignKey("inventory_master_ul.id", ondelete="CASCADE"), nullable=True)
    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    extra_data = Column(JSONB, default={})
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    external_system = relationship("ExternalSystem", back_populates="uas")
    ul = relationship("InventoryMasterUL", back_populates="uas")


class InventoryMasterPhysicalStatus(Base):
    """Situação Física de Bens - sincronizada do sistema externo"""
    __tablename__ = "inventory_master_physical_status"

    id = Column(Integer, primary_key=True, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    external_system = relationship("ExternalSystem", back_populates="physical_statuses")


class InventoryMasterCharacteristic(Base):
    """Características de Bens - sincronizada do sistema externo"""
    __tablename__ = "inventory_master_characteristics"

    id = Column(Integer, primary_key=True, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(String(30), nullable=True)  # text, number, date, list
    required = Column(Boolean, default=False)
    options = Column(JSONB, nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    external_system = relationship("ExternalSystem", back_populates="characteristics")


class InventoryMasterSyncLog(Base):
    """Log de sincronização de dados mestres"""
    __tablename__ = "inventory_master_sync_log"

    id = Column(Integer, primary_key=True, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id", ondelete="CASCADE"), nullable=False)
    sync_type = Column(String(30), nullable=False)  # ug, ul, ua, characteristics, physical_status
    status = Column(String(20), nullable=False, default=SyncStatus.RUNNING.value)
    items_received = Column(Integer, default=0)
    items_created = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    external_system = relationship("ExternalSystem", back_populates="sync_logs")
