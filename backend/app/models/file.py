from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class FileType(str, enum.Enum):
    INPUT_IMAGE = "INPUT_IMAGE"
    SCREENSHOT = "SCREENSHOT"
    PDF = "PDF"


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(SQLEnum(FileType), nullable=False)
    mime_type = Column(String(100), nullable=True)
    storage_path = Column(String(500), nullable=False)
    sha256 = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    quote_request_id = Column(Integer, ForeignKey("quote_requests.id"), nullable=True)
