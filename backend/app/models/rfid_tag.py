from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class RfidTagBatch(Base):
    """Lote de leitura de tags RFID do middleware mobile"""
    __tablename__ = "rfid_tag_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(100), unique=True, nullable=False, index=True)  # UUID do lote
    device_id = Column(String(100), nullable=False, index=True)  # Ex: R6-XX:XX:XX:XX:XX:XX
    location = Column(String(255), nullable=True)  # Local da leitura (opcional)

    # Relacionamento com projeto (opcional)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Usuario que enviou
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    tag_count = Column(Integer, default=0)  # Total de tags no lote

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    tags = relationship("RfidTag", back_populates="batch", cascade="all, delete-orphan")
    project = relationship("Project")
    user = relationship("User")


class RfidTag(Base):
    """Tag RFID individual lida pelo coletor"""
    __tablename__ = "rfid_tags"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("rfid_tag_batches.id", ondelete="CASCADE"), nullable=False, index=True)

    epc = Column(String(100), nullable=False, index=True)  # Codigo EPC da tag
    rssi = Column(String(20), nullable=True)  # Intensidade do sinal
    read_at = Column(DateTime(timezone=True), nullable=False)  # Timestamp da leitura no dispositivo

    # Campos para vincular com item do inventario (opcional)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True, index=True)
    matched = Column(Boolean, default=False)  # Se foi vinculado a um item

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    batch = relationship("RfidTagBatch", back_populates="tags")
    item = relationship("Item")

    # Index composto para busca rapida
    __table_args__ = (
        Index('ix_rfid_tags_epc_batch', 'epc', 'batch_id'),
    )
