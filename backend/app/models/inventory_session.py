"""
Models para Sessões de Inventário e Bens
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


class InventorySessionStatus(str, enum.Enum):
    """Status da sessão de inventário"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SYNCED = "synced"


class AssetCategory(str, enum.Enum):
    """Categorização de bens no inventário"""
    FOUND = "found"              # Bem esperado e encontrado
    NOT_FOUND = "not_found"      # Bem esperado mas não encontrado
    UNREGISTERED = "unregistered"  # Bem lido mas não cadastrado
    WRITTEN_OFF = "written_off"  # Bem baixado


class ReadMethod(str, enum.Enum):
    """Método de leitura do bem"""
    RFID = "rfid"
    BARCODE = "barcode"
    CAMERA = "camera"
    MANUAL = "manual"
    SYSTEM = "system"  # Gerado pelo sistema (ex: not_found)


class PhysicalCondition(str, enum.Enum):
    """Situação física do bem"""
    GOOD = "good"
    DAMAGED = "damaged"
    NEEDS_REPAIR = "needs_repair"
    UNUSABLE = "unusable"


class InventorySession(Base):
    """
    Sessão de Inventário (Levantamento)
    Representa uma sessão de coleta de inventário em uma localização específica
    """
    __tablename__ = "inventory_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    external_system_id = Column(Integer, ForeignKey("external_systems.id"), nullable=True)

    # Identificadores
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    external_id = Column(String(100), nullable=True)

    # Localização hierárquica (referências)
    ug_id = Column(Integer, ForeignKey("inventory_master_ug.id"), nullable=True)
    ul_id = Column(Integer, ForeignKey("inventory_master_ul.id"), nullable=True)
    ua_id = Column(Integer, ForeignKey("inventory_master_ua.id"), nullable=True)

    # Localização hierárquica (valores - para casos sem vínculo)
    ug_code = Column(String(50), nullable=True)
    ug_name = Column(String(200), nullable=True)
    ul_code = Column(String(50), nullable=True)
    ul_name = Column(String(200), nullable=True)
    ua_code = Column(String(50), nullable=True)
    ua_name = Column(String(200), nullable=True)

    # Geolocalização da UL (para validação)
    ul_latitude = Column(Numeric(10, 8), nullable=True)
    ul_longitude = Column(Numeric(11, 8), nullable=True)
    ul_radius_meters = Column(Integer, default=100)

    # Responsável
    responsible_name = Column(String(200), nullable=True)
    responsible_registration = Column(String(50), nullable=True)

    # Status
    status = Column(String(30), default=InventorySessionStatus.DRAFT.value)
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=True)

    # Estatísticas
    total_expected = Column(Integer, default=0)
    total_found = Column(Integer, default=0)
    total_not_found = Column(Integer, default=0)
    total_unregistered = Column(Integer, default=0)
    total_written_off = Column(Integer, default=0)

    # Campos para upload/sincronização com sistema externo
    external_transmission_number = Column(String(100), nullable=True)  # Número retornado pelo ASI
    external_inventory_id = Column(String(100), nullable=True)  # ID do levantamento no ASI
    external_uploaded_at = Column(DateTime(timezone=True), nullable=True)  # Data/hora do upload
    org_code = Column(String(20), nullable=True)  # Código do órgão (ASI)
    collector_id = Column(String(20), nullable=True)  # ID do coletor/dispositivo
    objective_code = Column(String(20), nullable=True, default='01')  # Código do objetivo
    responsible_code = Column(String(50), nullable=True)  # Código do responsável

    # Metadados
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    project = relationship("Project", back_populates="inventory_sessions")
    external_system = relationship("ExternalSystem")
    ug = relationship("InventoryMasterUG")
    ul = relationship("InventoryMasterUL")
    ua = relationship("InventoryMasterUA")
    creator = relationship("User")
    expected_assets = relationship("InventoryExpectedAsset", back_populates="session", cascade="all, delete-orphan")
    read_assets = relationship("InventoryReadAsset", back_populates="session", cascade="all, delete-orphan")
    sync_logs = relationship("InventorySyncLog", back_populates="session", cascade="all, delete-orphan")

    @property
    def total_read(self) -> int:
        """Total de bens lidos (encontrados + não cadastrados + baixados)"""
        return self.total_found + self.total_unregistered + self.total_written_off

    @property
    def progress_percentage(self) -> float:
        """Percentual de progresso do inventário"""
        if self.total_expected == 0:
            return 0.0
        return (self.total_read / self.total_expected) * 100

    def update_statistics(self):
        """Atualiza estatísticas baseado nos bens lidos"""
        from sqlalchemy import func as sql_func
        from sqlalchemy.orm import Session

        # Conta por categoria
        # Isso deve ser chamado com uma sessão de banco ativa
        pass  # Implementação será feita no service


class InventoryExpectedAsset(Base):
    """
    Bem Esperado (Carga)
    Representa um bem que deveria estar presente na localização inventariada
    """
    __tablename__ = "inventory_expected_assets"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inventory_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Identificadores do bem
    asset_code = Column(String(50), nullable=False, index=True)  # Plaqueta/Patrimônio
    asset_sequence = Column(String(20), nullable=True)  # Sequência (para bens com mesma plaqueta)
    rfid_code = Column(String(100), nullable=True, index=True)
    barcode = Column(String(100), nullable=True, index=True)

    # Descrição
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # Categoria do bem (móvel, equipamento, etc.)

    # Localização esperada
    expected_ul_code = Column(String(50), nullable=True)
    expected_ua_code = Column(String(50), nullable=True)

    # Situação no sistema externo
    is_written_off = Column(Boolean, default=False)

    # Status de processamento
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Dados extras do sistema externo
    extra_data = Column(JSONB, default={})

    # Relacionamentos
    session = relationship("InventorySession", back_populates="expected_assets")
    readings = relationship("InventoryReadAsset", back_populates="expected_asset")


class InventoryReadAsset(Base):
    """
    Bem Lido
    Representa um bem que foi lido/registrado durante o inventário
    """
    __tablename__ = "inventory_read_assets"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inventory_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    expected_asset_id = Column(Integer, ForeignKey("inventory_expected_assets.id", ondelete="SET NULL"), nullable=True, index=True)

    # Identificadores
    asset_code = Column(String(50), nullable=True)  # Plaqueta (pode ser digitada manualmente)
    rfid_code = Column(String(100), nullable=True)
    barcode = Column(String(100), nullable=True)

    # Método de leitura
    read_method = Column(String(20), nullable=False, default=ReadMethod.RFID.value)
    device_model = Column(String(50), nullable=True)  # Modelo do coletor

    # Categorização
    category = Column(String(30), nullable=False, default=AssetCategory.FOUND.value, index=True)

    # Situação física
    physical_condition = Column(String(30), nullable=True)
    physical_condition_code = Column(String(20), nullable=True)  # Código do sistema externo

    # Geolocalização da leitura
    read_latitude = Column(Numeric(10, 8), nullable=True)
    read_longitude = Column(Numeric(11, 8), nullable=True)
    geolocation_valid = Column(Boolean, nullable=True)  # Dentro do raio permitido?

    # Foto do bem
    photo_file_id = Column(String(100), nullable=True)
    photo_path = Column(String(500), nullable=True)

    # Observações
    notes = Column(Text, nullable=True)

    # Timestamp
    read_at = Column(DateTime(timezone=True), server_default=func.now())

    # Sincronização
    synced = Column(Boolean, default=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    external_status = Column(String(50), nullable=True)

    # Para modo offline
    local_id = Column(String(100), nullable=True)  # ID gerado localmente (IndexedDB)
    pending_sync = Column(Boolean, default=False, index=True)

    # Relacionamentos
    session = relationship("InventorySession", back_populates="read_assets")
    expected_asset = relationship("InventoryExpectedAsset", back_populates="readings")


class InventorySyncLog(Base):
    """
    Log de Sincronização de Sessão
    Registra histórico de download de carga e upload de resultados
    """
    __tablename__ = "inventory_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inventory_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_type = Column(String(20), nullable=False)  # download, upload
    status = Column(String(20), nullable=False)  # success, partial, failed
    items_sent = Column(Integer, nullable=True)
    items_success = Column(Integer, nullable=True)
    items_failed = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    response_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    session = relationship("InventorySession", back_populates="sync_logs")
