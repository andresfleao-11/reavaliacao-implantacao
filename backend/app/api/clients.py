from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.models import Client

router = APIRouter(prefix="/api/clients", tags=["clients"])


# Schemas
class ClientBase(BaseModel):
    nome: str
    nome_curto: Optional[str] = None
    cnpj: Optional[str] = None
    tipo_orgao: Optional[str] = None
    esfera: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    responsavel: Optional[str] = None
    observacoes: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    nome: Optional[str] = None
    nome_curto: Optional[str] = None
    cnpj: Optional[str] = None
    tipo_orgao: Optional[str] = None
    esfera: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    responsavel: Optional[str] = None
    observacoes: Optional[str] = None
    ativo: Optional[bool] = None


class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    ativo: bool
    total_projetos: int = 0

    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    items: List[ClientResponse]
    total: int
    page: int
    per_page: int


# Endpoints
@router.get("", response_model=ClientListResponse)
def list_clients(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    ativo: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Lista todos os clientes com paginação e filtros"""
    query = db.query(Client)

    if search:
        query = query.filter(
            Client.nome.ilike(f"%{search}%") |
            Client.cnpj.ilike(f"%{search}%") |
            Client.cidade.ilike(f"%{search}%")
        )

    if ativo is not None:
        query = query.filter(Client.ativo == ativo)

    total = query.count()

    clients = query.order_by(Client.nome).offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for client in clients:
        client_dict = {
            "id": client.id,
            "nome": client.nome,
            "nome_curto": client.nome_curto,
            "cnpj": client.cnpj,
            "tipo_orgao": client.tipo_orgao,
            "esfera": client.esfera,
            "endereco": client.endereco,
            "cidade": client.cidade,
            "uf": client.uf,
            "cep": client.cep,
            "telefone": client.telefone,
            "email": client.email,
            "responsavel": client.responsavel,
            "observacoes": client.observacoes,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
            "ativo": client.ativo,
            "total_projetos": len(client.projetos) if client.projetos else 0,
        }
        items.append(ClientResponse(**client_dict))

    return ClientListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Obtém um cliente específico"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    return ClientResponse(
        id=client.id,
        nome=client.nome,
        nome_curto=client.nome_curto,
        cnpj=client.cnpj,
        tipo_orgao=client.tipo_orgao,
        esfera=client.esfera,
        endereco=client.endereco,
        cidade=client.cidade,
        uf=client.uf,
        cep=client.cep,
        telefone=client.telefone,
        email=client.email,
        responsavel=client.responsavel,
        observacoes=client.observacoes,
        created_at=client.created_at,
        updated_at=client.updated_at,
        ativo=client.ativo,
        total_projetos=len(client.projetos) if client.projetos else 0,
    )


@router.post("", response_model=ClientResponse)
def create_client(client_data: ClientCreate, db: Session = Depends(get_db)):
    """Cria um novo cliente"""
    # Verificar CNPJ duplicado
    if client_data.cnpj:
        existing = db.query(Client).filter(Client.cnpj == client_data.cnpj).first()
        if existing:
            raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    client = Client(**client_data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)

    return ClientResponse(
        id=client.id,
        nome=client.nome,
        nome_curto=client.nome_curto,
        cnpj=client.cnpj,
        tipo_orgao=client.tipo_orgao,
        esfera=client.esfera,
        endereco=client.endereco,
        cidade=client.cidade,
        uf=client.uf,
        cep=client.cep,
        telefone=client.telefone,
        email=client.email,
        responsavel=client.responsavel,
        observacoes=client.observacoes,
        created_at=client.created_at,
        updated_at=client.updated_at,
        ativo=client.ativo,
        total_projetos=0,
    )


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: int, client_data: ClientUpdate, db: Session = Depends(get_db)):
    """Atualiza um cliente existente"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Verificar CNPJ duplicado
    if client_data.cnpj and client_data.cnpj != client.cnpj:
        existing = db.query(Client).filter(Client.cnpj == client_data.cnpj).first()
        if existing:
            raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    update_data = client_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)

    return ClientResponse(
        id=client.id,
        nome=client.nome,
        nome_curto=client.nome_curto,
        cnpj=client.cnpj,
        tipo_orgao=client.tipo_orgao,
        esfera=client.esfera,
        endereco=client.endereco,
        cidade=client.cidade,
        uf=client.uf,
        cep=client.cep,
        telefone=client.telefone,
        email=client.email,
        responsavel=client.responsavel,
        observacoes=client.observacoes,
        created_at=client.created_at,
        updated_at=client.updated_at,
        ativo=client.ativo,
        total_projetos=len(client.projetos) if client.projetos else 0,
    )


@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    """Remove um cliente (soft delete - apenas desativa)"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Verificar se tem projetos ativos
    if client.projetos:
        active_projects = [p for p in client.projetos if p.status not in ["CONCLUIDO", "CANCELADO"]]
        if active_projects:
            raise HTTPException(
                status_code=400,
                detail=f"Cliente possui {len(active_projects)} projeto(s) ativo(s). Conclua ou cancele os projetos antes de remover."
            )

    client.ativo = False
    db.commit()

    return {"message": "Cliente desativado com sucesso"}


@router.get("/options/list")
def get_client_options(db: Session = Depends(get_db)):
    """Retorna lista simplificada de clientes ativos para select/dropdown"""
    clients = db.query(Client).filter(Client.ativo == True).order_by(Client.nome).all()
    return [{"id": c.id, "nome": c.nome, "nome_curto": c.nome_curto} for c in clients]
