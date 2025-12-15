from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class UpdateMode(str, enum.Enum):
    MARKET = "MARKET"
    IPCA = "IPCA"
    MANUAL = "MANUAL"
    SKIP = "SKIP"


class BankPrice(Base):
    __tablename__ = "bank_prices"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(100), unique=True, nullable=False, index=True)
    material = Column(String(500), nullable=False)
    caracteristicas = Column(Text, nullable=True)
    vl_mercado = Column(Numeric(12, 2), nullable=True)
    update_mode = Column(SQLEnum(UpdateMode), default=UpdateMode.MARKET)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
