from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Client(Base):
    """
    Cliente - Órgão Público
    Representa um órgão público que contrata projetos de implantação
    """
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Dados básicos
    nome = Column(String(300), nullable=False, index=True)
    nome_curto = Column(String(100), nullable=True)  # Sigla ou nome abreviado
    cnpj = Column(String(20), nullable=True, unique=True, index=True)

    # Tipo de órgão
    tipo_orgao = Column(String(100), nullable=True)  # Federal, Estadual, Municipal, Autarquia, etc.
    esfera = Column(String(50), nullable=True)  # Executivo, Legislativo, Judiciário

    # Endereço
    endereco = Column(Text, nullable=True)
    cidade = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True)
    cep = Column(String(10), nullable=True)

    # Contato
    telefone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    responsavel = Column(String(200), nullable=True)  # Nome do responsável/gestor

    # Status
    ativo = Column(Boolean, default=True)

    # Observações
    observacoes = Column(Text, nullable=True)

    # Relacionamentos
    projetos = relationship("Project", back_populates="client", cascade="all, delete-orphan")
