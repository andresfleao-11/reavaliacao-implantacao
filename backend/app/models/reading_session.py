from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class ReadingType(str, enum.Enum):
    RFID = "RFID"
    BARCODE = "BARCODE"


class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"       # Aguardando leituras
    COMPLETED = "COMPLETED" # Finalizada com sucesso
    CANCELLED = "CANCELLED" # Cancelada pelo usuário
    EXPIRED = "EXPIRED"     # Expirada por timeout


class ReadingSession(Base):
    """
    Sessão de leitura - controla quando o app pode fazer leituras.
    Criada quando o usuário clica no botão de leitura na web.
    """
    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Tipo de leitura (RFID ou BARCODE)
    reading_type = Column(SQLEnum(ReadingType), nullable=False)

    # Status da sessão
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE)

    # Usuário que criou a sessão
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Projeto vinculado (opcional)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    # Local da leitura (opcional)
    location = Column(String(255), nullable=True)

    # Tempo de expiração em segundos (padrão 5 minutos)
    timeout_seconds = Column(Integer, default=300)

    # Relacionamentos
    user = relationship("User")
    project = relationship("Project")
    readings = relationship("SessionReading", back_populates="session", cascade="all, delete-orphan")


class SessionReading(Base):
    """
    Leitura individual dentro de uma sessão.
    """
    __tablename__ = "session_readings"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Sessão pai
    session_id = Column(Integer, ForeignKey("reading_sessions.id", ondelete="CASCADE"), nullable=False)

    # Código lido (EPC para RFID, código para barcode)
    code = Column(String(255), nullable=False)

    # RSSI (apenas para RFID)
    rssi = Column(String(20), nullable=True)

    # Device ID do leitor
    device_id = Column(String(100), nullable=True)

    # Relacionamentos
    session = relationship("ReadingSession", back_populates="readings")
