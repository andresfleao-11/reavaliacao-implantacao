from sqlalchemy import Column, Integer, JSON, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class RevaluationParam(Base):
    __tablename__ = "revaluation_params"

    id = Column(Integer, primary_key=True, index=True)
    ec_map_json = Column(JSON, nullable=False)
    pu_map_json = Column(JSON, nullable=False)
    vuf_map_json = Column(JSON, nullable=False)
    weights_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
