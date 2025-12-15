from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.models.material import Material, MaterialCharacteristic, Item, ItemCharacteristic, CharacteristicType
from app.models.client import Client
import csv
import io
import hashlib
import json
import pandas as pd
import re

router = APIRouter(prefix="/api/materials", tags=["materials"])


# ==================== SCHEMAS ====================

class CharacteristicBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    tipo_dado: str = "texto"  # texto, numero, data, lista
    opcoes: Optional[List[str]] = None  # Opções para tipo_dado="lista"


class CharacteristicCreate(CharacteristicBase):
    pass


class CharacteristicUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    tipo_dado: Optional[str] = None
    opcoes: Optional[List[str]] = None


class CharacteristicResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str] = None
    tipo_dado: str
    opcoes: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    client_id: Optional[int] = None
    codigo: Optional[str] = None  # Código numérico de 9 dígitos


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    client_id: Optional[int] = None
    codigo: Optional[str] = None
    ativo: Optional[bool] = None


class MaterialResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str] = None
    client_id: Optional[int] = None
    codigo: Optional[str] = None
    ativo: bool
    caracteristicas: List[CharacteristicResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialListResponse(BaseModel):
    items: List[MaterialResponse]
    total: int
    page: int
    per_page: int


# ==================== MATERIAL ENDPOINTS ====================

@router.get("", response_model=MaterialListResponse)
def list_materials(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    ativo: Optional[bool] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Lista todos os materiais com paginação e filtros"""
    query = db.query(Material)

    if ativo is not None:
        query = query.filter(Material.ativo == ativo)
    else:
        query = query.filter(Material.ativo == True)

    if client_id:
        query = query.filter(Material.client_id == client_id)

    if search:
        query = query.filter(
            (Material.nome.ilike(f"%{search}%")) |
            (Material.codigo.ilike(f"%{search}%"))
        )

    total = query.count()
    materials = query.order_by(Material.nome).offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for mat in materials:
        caracteristicas = [
            CharacteristicResponse(
                id=c.id,
                nome=c.nome,
                descricao=c.descricao,
                tipo_dado=c.tipo_dado,
                opcoes=c.opcoes_json,
                created_at=c.created_at
            ) for c in mat.caracteristicas
        ]
        items.append(MaterialResponse(
            id=mat.id,
            nome=mat.nome,
            descricao=mat.descricao,
            client_id=mat.client_id,
            codigo=mat.codigo,
            ativo=mat.ativo,
            caracteristicas=caracteristicas,
            created_at=mat.created_at,
            updated_at=mat.updated_at
        ))

    return MaterialListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{material_id}", response_model=MaterialResponse)
def get_material(material_id: int, db: Session = Depends(get_db)):
    """Obtém um material específico"""
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    caracteristicas = [
        CharacteristicResponse(
            id=c.id,
            nome=c.nome,
            descricao=c.descricao,
            tipo_dado=c.tipo_dado,
            opcoes=c.opcoes_json,
            created_at=c.created_at
        ) for c in mat.caracteristicas
    ]

    return MaterialResponse(
        id=mat.id,
        nome=mat.nome,
        descricao=mat.descricao,
        ativo=mat.ativo,
        caracteristicas=caracteristicas,
        created_at=mat.created_at,
        updated_at=mat.updated_at
    )


@router.post("", response_model=MaterialResponse)
def create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    """Cria um novo material"""
    mat = Material(
        nome=data.nome,
        descricao=data.descricao,
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)

    return MaterialResponse(
        id=mat.id,
        nome=mat.nome,
        descricao=mat.descricao,
        ativo=mat.ativo,
        caracteristicas=[],
        created_at=mat.created_at,
        updated_at=mat.updated_at
    )


@router.put("/{material_id}", response_model=MaterialResponse)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db)):
    """Atualiza um material"""
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mat, field, value)

    db.commit()
    db.refresh(mat)

    caracteristicas = [
        CharacteristicResponse(
            id=c.id,
            nome=c.nome,
            descricao=c.descricao,
            tipo_dado=c.tipo_dado,
            opcoes=c.opcoes_json,
            created_at=c.created_at
        ) for c in mat.caracteristicas
    ]

    return MaterialResponse(
        id=mat.id,
        nome=mat.nome,
        descricao=mat.descricao,
        ativo=mat.ativo,
        caracteristicas=caracteristicas,
        created_at=mat.created_at,
        updated_at=mat.updated_at
    )


@router.delete("/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    """Remove um material"""
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    # Remove características associadas
    db.query(MaterialCharacteristic).filter(MaterialCharacteristic.material_id == material_id).delete()

    db.delete(mat)
    db.commit()
    return {"message": "Material removido com sucesso"}


# ==================== CHARACTERISTIC ENDPOINTS ====================

@router.get("/{material_id}/characteristics", response_model=List[CharacteristicResponse])
def list_material_characteristics(material_id: int, db: Session = Depends(get_db)):
    """Lista características de um material"""
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    return [
        CharacteristicResponse(
            id=c.id,
            nome=c.nome,
            descricao=c.descricao,
            tipo_dado=c.tipo_dado,
            opcoes=c.opcoes_json,
            created_at=c.created_at
        ) for c in mat.caracteristicas
    ]


@router.post("/{material_id}/characteristics", response_model=CharacteristicResponse)
def create_characteristic(material_id: int, data: CharacteristicCreate, db: Session = Depends(get_db)):
    """Cria uma nova característica para um material"""
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    # Verificar duplicidade
    existing = db.query(MaterialCharacteristic).filter(
        MaterialCharacteristic.material_id == material_id,
        MaterialCharacteristic.nome == data.nome
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Característica já existe para este material")

    char = MaterialCharacteristic(
        material_id=material_id,
        nome=data.nome,
        descricao=data.descricao,
        tipo_dado=data.tipo_dado,
        opcoes_json=data.opcoes
    )
    db.add(char)
    db.commit()
    db.refresh(char)

    return CharacteristicResponse(
        id=char.id,
        nome=char.nome,
        descricao=char.descricao,
        tipo_dado=char.tipo_dado,
        opcoes=char.opcoes_json,
        created_at=char.created_at
    )


@router.put("/{material_id}/characteristics/{char_id}", response_model=CharacteristicResponse)
def update_characteristic(
    material_id: int,
    char_id: int,
    data: CharacteristicUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza uma característica"""
    char = db.query(MaterialCharacteristic).filter(
        MaterialCharacteristic.id == char_id,
        MaterialCharacteristic.material_id == material_id
    ).first()
    if not char:
        raise HTTPException(status_code=404, detail="Característica não encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'opcoes':
            char.opcoes_json = value
        else:
            setattr(char, field, value)

    db.commit()
    db.refresh(char)

    return CharacteristicResponse(
        id=char.id,
        nome=char.nome,
        descricao=char.descricao,
        tipo_dado=char.tipo_dado,
        opcoes=char.opcoes_json,
        created_at=char.created_at
    )


@router.delete("/{material_id}/characteristics/{char_id}")
def delete_characteristic(material_id: int, char_id: int, db: Session = Depends(get_db)):
    """Remove uma característica"""
    char = db.query(MaterialCharacteristic).filter(
        MaterialCharacteristic.id == char_id,
        MaterialCharacteristic.material_id == material_id
    ).first()
    if not char:
        raise HTTPException(status_code=404, detail="Característica não encontrada")

    db.delete(char)
    db.commit()
    return {"message": "Característica removida"}


# ==================== IMPORT ENDPOINTS (DEPRECATED - moved to line 800) ====================
# O endpoint de import foi movido para linha 800 com suporte a CSV/XLSX e características


# ==================== OPTIONS ENDPOINTS ====================

@router.get("/options/list")
def get_material_options(db: Session = Depends(get_db)):
    """Retorna lista simplificada de materiais para select"""
    materials = db.query(Material).filter(Material.ativo == True).order_by(Material.nome).all()
    return [{"id": m.id, "nome": m.nome} for m in materials]


@router.get("/options/characteristic-types")
def get_characteristic_types(db: Session = Depends(get_db)):
    """Retorna lista de tipos de características"""
    types = db.query(CharacteristicType).order_by(CharacteristicType.nome).all()
    return [{"id": t.id, "nome": t.nome} for t in types]


# ==================== ITEM SCHEMAS ====================

class ItemCharacteristicInput(BaseModel):
    tipo_id: int
    valor: str


class ItemCharacteristicResponse(BaseModel):
    id: int
    tipo_id: int
    tipo_nome: str
    valor: str

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    client_id: Optional[int] = None
    material_id: int
    codigo: Optional[str] = None
    patrimonio: Optional[str] = None
    project_id: Optional[int] = None
    status: str = "DISPONIVEL"
    localizacao: Optional[str] = None
    observacoes: Optional[str] = None


class ItemCreate(ItemBase):
    caracteristicas: List[ItemCharacteristicInput] = []


class ItemUpdate(BaseModel):
    client_id: Optional[int] = None
    codigo: Optional[str] = None
    patrimonio: Optional[str] = None
    project_id: Optional[int] = None
    status: Optional[str] = None
    localizacao: Optional[str] = None
    observacoes: Optional[str] = None


class ItemResponse(BaseModel):
    id: int
    client_id: Optional[int]
    material_id: int
    material_nome: str
    codigo: Optional[str]
    patrimonio: Optional[str]
    project_id: Optional[int]
    status: str
    localizacao: Optional[str]
    observacoes: Optional[str]
    caracteristicas: List[ItemCharacteristicResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class ItemListResponse(BaseModel):
    items: List[ItemResponse]
    total: int
    page: int
    per_page: int


# ==================== ITEM ENDPOINTS ====================

@router.get("/items/list", response_model=ItemListResponse)
def list_items(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    material_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lista todos os itens com paginação e filtros"""
    query = db.query(Item)

    if material_id:
        query = query.filter(Item.material_id == material_id)

    if status:
        query = query.filter(Item.status == status)

    if search:
        query = query.filter(
            (Item.codigo.ilike(f"%{search}%")) |
            (Item.patrimonio.ilike(f"%{search}%"))
        )

    total = query.count()
    items = query.order_by(Item.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    items_response = []
    for item in items:
        caracteristicas = []
        for c in item.caracteristicas:
            caracteristicas.append(ItemCharacteristicResponse(
                id=c.id,
                tipo_id=c.tipo_id,
                tipo_nome=c.tipo.nome if c.tipo else "",
                valor=c.valor
            ))

        items_response.append(ItemResponse(
            id=item.id,
            client_id=item.client_id,
            material_id=item.material_id,
            material_nome=item.material.nome if item.material else "",
            codigo=item.codigo,
            patrimonio=item.patrimonio,
            project_id=item.project_id,
            status=item.status,
            localizacao=item.localizacao,
            observacoes=item.observacoes,
            caracteristicas=caracteristicas,
            created_at=item.created_at
        ))

    return ItemListResponse(items=items_response, total=total, page=page, per_page=per_page)


@router.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    """Obtém um item específico"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    caracteristicas = []
    for c in item.caracteristicas:
        caracteristicas.append(ItemCharacteristicResponse(
            id=c.id,
            tipo_id=c.tipo_id,
            tipo_nome=c.tipo.nome if c.tipo else "",
            valor=c.valor
        ))

    return ItemResponse(
        id=item.id,
        client_id=item.client_id,
        material_id=item.material_id,
        material_nome=item.material.nome if item.material else "",
        codigo=item.codigo,
        patrimonio=item.patrimonio,
        project_id=item.project_id,
        status=item.status,
        localizacao=item.localizacao,
        observacoes=item.observacoes,
        caracteristicas=caracteristicas,
        created_at=item.created_at
    )


@router.post("/items", response_model=ItemResponse)
def create_item(data: ItemCreate, db: Session = Depends(get_db)):
    """Cria um novo item"""
    # Verificar se material existe
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    # Verificar se patrimônio já existe
    if data.patrimonio:
        existing = db.query(Item).filter(Item.patrimonio == data.patrimonio).first()
        if existing:
            raise HTTPException(status_code=400, detail="Número de patrimônio já existe")

    # Calcular hash das características
    char_hash = None
    if data.caracteristicas:
        chars_dict = [{"tipo_id": c.tipo_id, "valor": c.valor} for c in data.caracteristicas]
        char_hash = calculate_characteristics_hash(chars_dict)

        # Verificar se já existe item com mesmas características
        existing = db.query(Item).filter(
            Item.client_id == data.client_id,
            Item.material_id == data.material_id,
            Item.caracteristicas_hash == char_hash
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Já existe um item com este material e características (Item ID: {existing.id})"
            )

    # Criar item
    item = Item(
        client_id=data.client_id,
        material_id=data.material_id,
        codigo=data.codigo,
        patrimonio=data.patrimonio,
        project_id=data.project_id,
        status=data.status,
        localizacao=data.localizacao,
        observacoes=data.observacoes,
        caracteristicas_hash=char_hash
    )
    db.add(item)
    db.flush()

    # Adicionar características
    for char in data.caracteristicas:
        item_char = ItemCharacteristic(
            item_id=item.id,
            tipo_id=char.tipo_id,
            valor=char.valor
        )
        db.add(item_char)

    db.commit()
    db.refresh(item)

    return get_item(item.id, db)


@router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, data: ItemUpdate, db: Session = Depends(get_db)):
    """Atualiza um item"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    # Verificar se patrimônio já existe (se estiver sendo alterado)
    if data.patrimonio and data.patrimonio != item.patrimonio:
        existing = db.query(Item).filter(
            Item.patrimonio == data.patrimonio,
            Item.id != item_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Número de patrimônio já existe")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)

    return get_item(item.id, db)


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Remove um item"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    db.delete(item)
    db.commit()
    return {"message": "Item removido com sucesso"}


@router.get("/items/status/options")
def get_status_options():
    """Retorna lista de status disponíveis para itens"""
    return [
        {"value": "DISPONIVEL", "label": "Disponível"},
        {"value": "EM_USO", "label": "Em Uso"},
        {"value": "MANUTENCAO", "label": "Manutenção"},
        {"value": "BAIXADO", "label": "Baixado"},
        {"value": "TRANSFERIDO", "label": "Transferido"}
    ]


# ==================== GERAÇÃO EM LOTE ====================

class BulkItemCreate(BaseModel):
    client_id: int
    material_id: int
    items: List[List[Dict[str, str]]]  # Lista de listas de características {nome: str, valor: str}
    codigo_inicial: Optional[str] = None


@router.post("/items/bulk-create")
def bulk_create_items(data: BulkItemCreate, db: Session = Depends(get_db)):
    """
    Cria múltiplos itens em lote
    Gera códigos sequenciais para cada item
    """
    # Verificar se material existe
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    # Verificar se cliente existe
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    created = 0
    skipped = 0
    errors = []

    # Gerar códigos sequenciais
    if data.codigo_inicial:
        # Extrair parte numérica e não-numérica do código inicial
        import re
        match = re.match(r'([^\d]*)(\d+)', data.codigo_inicial)
        if match:
            prefix = match.group(1)
            start_num = int(match.group(2))
            num_length = len(match.group(2))
        else:
            prefix = data.codigo_inicial
            start_num = 1
            num_length = 3
    else:
        # Código automático sequencial
        prefix = "ITEM"
        start_num = 1
        num_length = 6

    for idx, item_chars in enumerate(data.items):
        try:
            # Gerar código para este item
            codigo_numero = start_num + idx
            codigo = f"{prefix}{str(codigo_numero).zfill(num_length)}"

            # Converter características de nome para tipo_id
            caracteristicas_com_id = []
            for char_dict in item_chars:
                char_nome = char_dict.get('nome')
                char_valor = char_dict.get('valor')

                if not char_nome or not char_valor:
                    continue

                # Buscar CharacteristicType pelo nome
                char_type = db.query(CharacteristicType).filter(
                    CharacteristicType.nome == char_nome
                ).first()

                if char_type:
                    caracteristicas_com_id.append({
                        "tipo_id": char_type.id,
                        "valor": char_valor
                    })

            # Calcular hash das características
            char_hash = None
            if caracteristicas_com_id:
                char_hash = calculate_characteristics_hash(caracteristicas_com_id)

                # Verificar se item já existe (mesmas características)
                existing = db.query(Item).filter(
                    Item.client_id == data.client_id,
                    Item.material_id == data.material_id,
                    Item.caracteristicas_hash == char_hash
                ).first()

                if existing:
                    skipped += 1
                    continue

            # Criar item
            new_item = Item(
                client_id=data.client_id,
                material_id=data.material_id,
                codigo=codigo,
                status='DISPONIVEL',
                caracteristicas_hash=char_hash
            )
            db.add(new_item)
            db.flush()

            # Adicionar características
            for char_data in caracteristicas_com_id:
                item_char = ItemCharacteristic(
                    item_id=new_item.id,
                    tipo_id=char_data['tipo_id'],
                    valor=char_data['valor']
                )
                db.add(item_char)

            created += 1

        except Exception as e:
            errors.append(f"Item {idx + 1}: {str(e)}")

    db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors
    }


# ==================== GERAÇÃO DE ITENS ====================

def calculate_characteristics_hash(caracteristicas: List[dict]) -> str:
    """
    Calcula hash SHA256 das características ordenadas por tipo_id
    Para validar unicidade de item (material + características)
    """
    # Ordenar por tipo_id para garantir consistência
    sorted_chars = sorted(caracteristicas, key=lambda x: x['tipo_id'])

    # Criar string com tipo_id:valor
    chars_str = "|".join([f"{c['tipo_id']}:{c['valor']}" for c in sorted_chars])

    # Calcular hash
    return hashlib.sha256(chars_str.encode()).hexdigest()


class GenerateItemsRequest(BaseModel):
    """Request para gerar itens a partir de um material"""
    material_id: int
    client_id: Optional[int] = None
    caracteristicas_set: List[List[ItemCharacteristicInput]]  # Lista de conjuntos de características


class GenerateItemsResponse(BaseModel):
    created: int  # Itens criados
    skipped: int  # Itens já existentes (duplicados)
    errors: List[str]  # Erros encontrados
    items: List[ItemResponse]  # Itens criados


@router.post("/items/generate", response_model=GenerateItemsResponse)
def generate_items_from_material(data: GenerateItemsRequest, db: Session = Depends(get_db)):
    """
    Gera itens a partir de um material e conjuntos de características

    Valida unicidade: não cria item duplicado se já existir item com:
    - Mesmo client_id
    - Mesmo material_id
    - Mesmas características (hash)
    """
    # Verificar se material existe
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    created = 0
    skipped = 0
    errors = []
    created_items = []

    for idx, caracteristicas_input in enumerate(data.caracteristicas_set, start=1):
        try:
            # Converter para dict para cálculo de hash
            chars_dict = [{"tipo_id": c.tipo_id, "valor": c.valor} for c in caracteristicas_input]

            # Calcular hash das características
            char_hash = calculate_characteristics_hash(chars_dict)

            # Verificar se já existe item com mesmo material + características + cliente
            existing = db.query(Item).filter(
                Item.client_id == data.client_id,
                Item.material_id == data.material_id,
                Item.caracteristicas_hash == char_hash
            ).first()

            if existing:
                skipped += 1
                continue

            # Criar novo item
            item = Item(
                client_id=data.client_id,
                material_id=data.material_id,
                caracteristicas_hash=char_hash,
                status="DISPONIVEL"
            )
            db.add(item)
            db.flush()

            # Adicionar características
            for char_input in caracteristicas_input:
                item_char = ItemCharacteristic(
                    item_id=item.id,
                    tipo_id=char_input.tipo_id,
                    valor=char_input.valor
                )
                db.add(item_char)

            db.flush()
            created += 1

            # Adicionar à lista de criados
            created_items.append(get_item(item.id, db))

        except Exception as e:
            errors.append(f"Conjunto {idx}: {str(e)}")

    db.commit()

    return GenerateItemsResponse(
        created=created,
        skipped=skipped,
        errors=errors,
        items=created_items
    )


# ==================== MATERIAL SUGGESTION ====================

class MaterialSuggestionRequest(BaseModel):
    """Request para sugestão de materiais baseado em especificações"""
    especificacoes_tecnicas: Dict[str, str]  # Ex: {"marca": "Dell", "modelo": "Latitude 5410", ...}
    tipo_produto: Optional[str] = None  # Ex: "notebook", "ar condicionado"
    project_id: Optional[int] = None  # Para filtrar por cliente do projeto


class SuggestedMaterialResponse(BaseModel):
    """Material sugerido com score de similaridade"""
    id: int
    nome: str
    descricao: Optional[str]
    codigo: Optional[str]
    categoria: Optional[str]
    marca: Optional[str]
    caracteristicas: List[CharacteristicResponse]
    similarity_score: float  # 0-100, quanto maior melhor match
    matched_specs: List[str]  # Quais specs foram matcheadas

    class Config:
        from_attributes = True


class MaterialSuggestionResponse(BaseModel):
    """Resposta com lista de materiais sugeridos ordenados por relevância"""
    suggestions: List[SuggestedMaterialResponse]
    total_found: int


@router.post("/suggest", response_model=MaterialSuggestionResponse)
def suggest_materials(data: MaterialSuggestionRequest, db: Session = Depends(get_db)):
    """
    Sugere materiais baseado nas especificações técnicas detectadas

    Algoritmo:
    1. Filtra materiais ativos (opcionalmente por cliente)
    2. Calcula score de similaridade baseado em:
       - Match de marca (peso 30%)
       - Match de categoria/tipo (peso 25%)
       - Match de características (peso 45%)
    3. Retorna top 5 materiais ordenados por score
    """
    specs = data.especificacoes_tecnicas

    # Buscar materiais ativos
    query = db.query(Material).filter(Material.ativo == True)

    # Se tiver project_id, filtrar por cliente
    if data.project_id:
        from app.models import Project
        project = db.query(Project).filter(Project.id == data.project_id).first()
        if project and project.client_id:
            query = query.filter(Material.client_id == project.client_id)

    materials = query.all()

    # Calcular score para cada material
    scored_materials = []

    for material in materials:
        score = 0.0
        matched_specs = []

        # 1. Match de marca (30 pontos)
        if material.marca and 'marca' in specs:
            marca_spec = specs['marca'].lower()
            marca_material = material.marca.lower()
            if marca_spec in marca_material or marca_material in marca_spec:
                score += 30
                matched_specs.append(f"Marca: {material.marca}")

        # 2. Match de tipo/categoria (25 pontos)
        if data.tipo_produto:
            tipo_produto_lower = data.tipo_produto.lower()
            # Verificar categoria
            if material.categoria and tipo_produto_lower in material.categoria.lower():
                score += 15
                matched_specs.append(f"Categoria: {material.categoria}")
            # Verificar tipo
            if material.tipo and tipo_produto_lower in material.tipo.lower():
                score += 10
                matched_specs.append(f"Tipo: {material.tipo}")
            # Verificar nome
            if tipo_produto_lower in material.nome.lower():
                score += 10
                matched_specs.append(f"Nome: {material.nome}")

        # 3. Match de características (até 45 pontos)
        material_chars = {c.nome.lower(): c for c in material.caracteristicas}
        max_char_score = 45
        char_matches = 0
        total_specs_to_check = len([k for k in specs.keys() if k not in ['marca', 'tipo']])

        if total_specs_to_check > 0:
            char_score_per_match = max_char_score / total_specs_to_check

            for spec_key, spec_value in specs.items():
                if spec_key.lower() in ['marca', 'tipo']:
                    continue

                spec_key_lower = spec_key.lower()

                # Verificar se característica existe no material
                if spec_key_lower in material_chars:
                    char_matches += 1
                    score += char_score_per_match
                    matched_specs.append(f"{spec_key}: {spec_value}")
                else:
                    # Verificar match parcial (ex: "processador" match "proc")
                    for mat_char_name in material_chars.keys():
                        if spec_key_lower in mat_char_name or mat_char_name in spec_key_lower:
                            char_matches += 1
                            score += char_score_per_match * 0.5  # Score reduzido para match parcial
                            matched_specs.append(f"{spec_key}: {spec_value} (parcial)")
                            break

        # Só adicionar se houver algum match
        if score > 0:
            # Preparar características para resposta
            caracteristicas = [
                CharacteristicResponse(
                    id=c.id,
                    nome=c.nome,
                    descricao=c.descricao,
                    tipo_dado=c.tipo_dado,
                    opcoes=c.opcoes_json,
                    created_at=c.created_at
                ) for c in material.caracteristicas
            ]

            scored_materials.append(SuggestedMaterialResponse(
                id=material.id,
                nome=material.nome,
                descricao=material.descricao,
                codigo=material.codigo,
                categoria=material.categoria,
                marca=material.marca,
                caracteristicas=caracteristicas,
                similarity_score=round(score, 2),
                matched_specs=matched_specs
            ))

    # Ordenar por score (maior primeiro) e pegar top 5
    scored_materials.sort(key=lambda x: x.similarity_score, reverse=True)
    top_suggestions = scored_materials[:5]

    return MaterialSuggestionResponse(
        suggestions=top_suggestions,
        total_found=len(scored_materials)
    )


# ==================== IMPORT CSV/XLSX ====================

class ImportMaterialsResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]


@router.post("/import", response_model=ImportMaterialsResponse)
async def import_materials_from_file(
    file: UploadFile = File(...),
    client_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Importa materiais e itens a partir de arquivo CSV ou XLSX

    Formato esperado:
    - Coluna 1: Código do material (9 dígitos)
    - Coluna 2: Nome do material
    - Coluna 3: Características no formato "CARACTERISTICA1: VALOR1, CARACTERISTICA2: VALOR2, ..."

    Se o material já existir (mesmo código), suas características serão atualizadas.
    Para cada linha, cria-se um item com as características especificadas.
    """
    created = 0
    updated = 0
    skipped = 0
    errors = []

    try:
        # Ler arquivo
        content = await file.read()

        # Detectar formato e processar
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content), header=None, names=['codigo', 'material', 'caracteristicas'])
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(content), header=None, names=['codigo', 'material', 'caracteristicas'])
        else:
            raise HTTPException(status_code=400, detail="Formato de arquivo não suportado. Use CSV ou XLSX.")

        # Processar cada linha
        for idx, row in df.iterrows():
            try:
                codigo = str(row['codigo']).strip()
                material_nome = str(row['material']).strip()
                caracteristicas_str = str(row['caracteristicas']).strip() if pd.notna(row['caracteristicas']) else ''

                # Validar código (9 dígitos)
                if not re.match(r'^\d{9}$', codigo):
                    errors.append(f"Linha {idx+1}: Código inválido '{codigo}' (deve ter 9 dígitos)")
                    skipped += 1
                    continue

                if not material_nome or material_nome == 'nan':
                    errors.append(f"Linha {idx+1}: Nome do material vazio")
                    skipped += 1
                    continue

                # Verificar se material já existe (por código OU por nome+cliente)
                material = db.query(Material).filter(Material.codigo == codigo).first()

                if not material:
                    # Se não encontrou por código, buscar por nome e cliente
                    material = db.query(Material).filter(
                        Material.nome == material_nome,
                        Material.client_id == client_id
                    ).first()

                if material:
                    # Material já existe - apenas garantir que código e nome estão corretos
                    if not material.codigo:
                        material.codigo = codigo
                    if material.nome != material_nome:
                        material.nome = material_nome
                    material.client_id = client_id
                    # Não conta como updated pois o material já existia
                else:
                    # Criar novo material
                    material = Material(
                        nome=material_nome,
                        codigo=codigo,
                        client_id=client_id,
                        ativo=True
                    )
                    db.add(material)
                    db.flush()  # Para obter o ID
                    created += 1

                # Processar características se fornecidas
                if caracteristicas_str and caracteristicas_str != 'nan':
                    # Parse: "CAR1: VAL1, CAR2: VAL2, ..."
                    caracteristicas_dict = {}
                    for item in caracteristicas_str.split(','):
                        if ':' in item:
                            key, value = item.split(':', 1)
                            caracteristicas_dict[key.strip()] = value.strip()

                    # Criar tipos de características se não existirem E associar ao material
                    for char_nome, char_valor in caracteristicas_dict.items():
                        # Criar CharacteristicType (tabela global de tipos)
                        char_type = db.query(CharacteristicType).filter(
                            CharacteristicType.nome == char_nome
                        ).first()

                        if not char_type:
                            char_type = CharacteristicType(
                                nome=char_nome,
                                descricao=f"Importado automaticamente",
                                tipo_dado="lista"  # Usar lista para suportar múltiplos valores
                            )
                            db.add(char_type)
                            db.flush()

                        # Associar característica ao material se ainda não existir
                        # MaterialCharacteristic define quais características o material aceita
                        existing_mat_char = db.query(MaterialCharacteristic).filter(
                            MaterialCharacteristic.material_id == material.id,
                            MaterialCharacteristic.nome == char_nome
                        ).first()

                        if not existing_mat_char:
                            # Criar com o primeiro valor encontrado nas opções
                            mat_char = MaterialCharacteristic(
                                material_id=material.id,
                                nome=char_nome,
                                descricao=f"Importado automaticamente",
                                tipo_dado="lista",
                                opcoes_json=[char_valor]  # Iniciar com o primeiro valor
                            )
                            db.add(mat_char)
                        else:
                            # Atualizar opções se o valor ainda não existir
                            opcoes_atuais = existing_mat_char.opcoes_json or []
                            if char_valor not in opcoes_atuais:
                                opcoes_atuais.append(char_valor)
                                existing_mat_char.opcoes_json = opcoes_atuais
                                # Forçar atualização do campo JSON
                                from sqlalchemy.orm.attributes import flag_modified
                                flag_modified(existing_mat_char, "opcoes_json")

                    # Criar item com as características
                    # Preparar características para o item
                    item_chars = []
                    for char_nome, char_valor in caracteristicas_dict.items():
                        char_type = db.query(CharacteristicType).filter(
                            CharacteristicType.nome == char_nome
                        ).first()
                        if char_type:
                            item_chars.append({
                                "tipo_id": char_type.id,
                                "valor": char_valor
                            })

                    # Calcular hash para validar unicidade
                    char_hash = calculate_characteristics_hash(item_chars) if item_chars else None

                    # Verificar se item já existe (mesmas características)
                    if char_hash:
                        existing_item = db.query(Item).filter(
                            Item.client_id == client_id,
                            Item.material_id == material.id,
                            Item.caracteristicas_hash == char_hash
                        ).first()

                        if not existing_item:
                            # Criar novo item
                            new_item = Item(
                                client_id=client_id,
                                material_id=material.id,
                                codigo=codigo,
                                status='DISPONIVEL',
                                caracteristicas_hash=char_hash
                            )
                            db.add(new_item)
                            db.flush()

                            # Adicionar características ao item
                            for char_data in item_chars:
                                item_char = ItemCharacteristic(
                                    item_id=new_item.id,
                                    tipo_id=char_data['tipo_id'],
                                    valor=char_data['valor']
                                )
                                db.add(item_char)

            except Exception as e:
                errors.append(f"Linha {idx+1}: {str(e)}")
                skipped += 1

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")

    return ImportMaterialsResponse(
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors
    )
