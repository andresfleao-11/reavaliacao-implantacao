from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class CharacteristicScope(str, enum.Enum):
    """
    Define se a característica é genérica (pode ser usada em vários materiais)
    ou específica (exclusiva para um tipo de bem)
    """
    GENERICA = "GENERICA"      # Pode ser usada para qualquer material (ex: cor, peso)
    ESPECIFICA = "ESPECIFICA"  # Específica para certo tipo de bem (ex: número de série)


class CharacteristicType(Base):
    """
    Tipo de Característica
    Define os tipos de características que podem ser associados aos materiais
    Ex: Número de Série, Cor, Voltagem, Capacidade, etc.
    """
    __tablename__ = "characteristic_types"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    nome = Column(String(100), nullable=False, unique=True, index=True)
    descricao = Column(Text, nullable=True)

    # Escopo: GENERICA ou ESPECIFICA
    escopo = Column(SQLEnum(CharacteristicScope), default=CharacteristicScope.GENERICA)

    # Tipo de dado esperado (para validação futura)
    tipo_dado = Column(String(50), default="texto")  # texto, numero, data, lista

    # Se específica, para qual tipo de material
    tipo_material_especifico = Column(String(100), nullable=True)  # Ex: "NOTEBOOK", "AR_CONDICIONADO"

    # Se requer valor único por item (ex: número de série)
    valor_unico = Column(Boolean, default=False)

    # Status
    ativo = Column(Boolean, default=True)


class Material(Base):
    """
    Material
    Representa um tipo de material/produto catalogado
    Ex: Notebook Dell, Ar Condicionado Springer, etc.
    """
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Vinculação com cliente
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)

    # Identificação
    codigo = Column(String(9), nullable=True, index=True)  # Código numérico de 9 dígitos
    nome = Column(String(300), nullable=False, index=True)
    descricao = Column(Text, nullable=True)

    # Categorização
    categoria = Column(String(100), nullable=True, index=True)  # Ex: Informática, Climatização
    subcategoria = Column(String(100), nullable=True)  # Ex: Notebooks, Ar Condicionado Split
    tipo = Column(String(100), nullable=True)  # Ex: NOTEBOOK, AR_CONDICIONADO

    # Marca/Fabricante
    marca = Column(String(100), nullable=True)
    fabricante = Column(String(200), nullable=True)

    # Unidade de medida
    unidade = Column(String(20), default="UN")  # UN, CX, KG, etc.

    # Status
    ativo = Column(Boolean, default=True)

    # Relacionamentos
    client = relationship("Client")
    caracteristicas = relationship("MaterialCharacteristic", back_populates="material", cascade="all, delete-orphan")
    itens = relationship("Item", back_populates="material", cascade="all, delete-orphan")


class MaterialCharacteristic(Base):
    """
    Característica do Material
    Define as características que um material pode ter
    Ex: Material "Notebook" -> Característica "Processador", "Memória RAM", etc.
    """
    __tablename__ = "material_characteristics"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Vinculação com material
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)

    # Dados da característica
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    tipo_dado = Column(String(50), default="texto")  # texto, numero, data, lista

    # Opções predefinidas (para tipo_dado="lista")
    # Formato: ["Dell", "Lenovo", "HP", "Asus"]
    opcoes_json = Column(JSON, nullable=True)

    # Relacionamentos
    material = relationship("Material", back_populates="caracteristicas")


class Item(Base):
    """
    Item
    Representa uma instância específica de um material com suas características próprias
    Um material pode ter vários itens (ex: 10 notebooks Dell iguais, cada um com seu número de série)
    """
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Vinculação com cliente
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)

    # Vinculação com material base
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)

    # Identificação do item
    codigo = Column(String(100), nullable=True, index=True)  # Código único do item
    patrimonio = Column(String(50), nullable=True, unique=True, index=True)  # Número de patrimônio

    # Vinculação com projeto (opcional)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)

    # Status do item
    status = Column(String(50), default="DISPONIVEL")  # DISPONIVEL, EM_USO, BAIXADO, etc.

    # Localização
    localizacao = Column(String(200), nullable=True)

    # Observações
    observacoes = Column(Text, nullable=True)

    # Hash para validação de unicidade (material + características)
    caracteristicas_hash = Column(String(64), nullable=True, index=True)

    # Relacionamentos
    client = relationship("Client")
    material = relationship("Material", back_populates="itens")
    project = relationship("Project")
    caracteristicas = relationship("ItemCharacteristic", back_populates="item", cascade="all, delete-orphan")


class ItemCharacteristic(Base):
    """
    Característica do Item
    Valores específicos de características para um item individual
    Ex: Item (Notebook #1) -> "Número de Série" = "ABC123XYZ"
    """
    __tablename__ = "item_characteristics"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Vinculações
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    tipo_id = Column(Integer, ForeignKey("characteristic_types.id"), nullable=False, index=True)

    # Valor da característica
    valor = Column(Text, nullable=False)

    # Relacionamentos
    item = relationship("Item", back_populates="caracteristicas")
    tipo = relationship("CharacteristicType")
