from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class VehiclePriceBank(Base):
    """
    Banco de Precos de Veiculos - Armazena cotacoes FIPE realizadas pelo sistema.

    Permite:
    - Rastreabilidade de cotacoes
    - Atualizacao para mes vigente
    - Historico de consultas
    - Reutilizacao de cotacoes
    """
    __tablename__ = "vehicle_price_bank"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Identificadores FIPE
    codigo_fipe = Column(String(15), nullable=False, index=True)  # Ex: "001267-9"
    brand_id = Column(Integer, nullable=False)
    brand_name = Column(String(100), nullable=False)
    model_id = Column(Integer, nullable=False)
    model_name = Column(String(200), nullable=False)
    year_id = Column(String(10), nullable=False)  # Ex: "2020-1"
    year_model = Column(Integer, nullable=False)  # Ex: 2020
    fuel_type = Column(String(30), nullable=False)  # Ex: "Gasolina", "Flex", "Diesel"
    fuel_code = Column(Integer, nullable=False)  # 1, 2 ou 3

    # Dados do Veiculo
    vehicle_type = Column(String(20), nullable=False, default="cars")  # cars, motorcycles, trucks
    vehicle_name = Column(String(300), nullable=False)  # Nome completo do veiculo

    # Preco e Referencia
    price_value = Column(Numeric(12, 2), nullable=False)
    reference_month = Column(String(30), nullable=False)  # Ex: "dezembro de 2024"
    reference_date = Column(Date, nullable=False)  # Ex: 2024-12-01

    # Rastreabilidade
    quote_request_id = Column(Integer, ForeignKey("quote_requests.id"), nullable=True)
    api_response_json = Column(JSON, nullable=True)  # Resposta bruta da API
    last_api_call = Column(DateTime(timezone=True), nullable=True)

    # Screenshot da consulta FIPE
    screenshot_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    screenshot_path = Column(String(500), nullable=True)  # Caminho do screenshot

    # Relacionamentos
    quote_request = relationship("QuoteRequest", backref="vehicle_prices")
    screenshot_file = relationship("File", foreign_keys=[screenshot_file_id])

    # Constraint de unicidade para evitar duplicatas
    __table_args__ = (
        UniqueConstraint('codigo_fipe', 'year_id', name='uq_vehicle_fipe_year'),
    )

    def __repr__(self):
        return f"<VehiclePriceBank {self.codigo_fipe} - {self.vehicle_name} - R$ {self.price_value}>"
