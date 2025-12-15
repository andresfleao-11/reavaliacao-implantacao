from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from app.core.database import get_db
from app.models import Project, ProjectStatus, Client

router = APIRouter(prefix="/api/projects", tags=["projects"])


# Schemas
class ProjectBase(BaseModel):
    client_id: int
    nome: str
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    numero_contrato: Optional[str] = None
    numero_processo: Optional[str] = None
    modalidade_licitacao: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_previsao_fim: Optional[datetime] = None
    valor_contrato: Optional[Decimal] = None
    responsavel_tecnico: Optional[str] = None
    responsavel_cliente: Optional[str] = None
    observacoes: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    client_id: Optional[int] = None
    nome: Optional[str] = None
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    numero_contrato: Optional[str] = None
    numero_processo: Optional[str] = None
    modalidade_licitacao: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_previsao_fim: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    valor_contrato: Optional[Decimal] = None
    status: Optional[str] = None
    responsavel_tecnico: Optional[str] = None
    responsavel_cliente: Optional[str] = None
    observacoes: Optional[str] = None


class ClientInfo(BaseModel):
    id: int
    nome: str
    nome_curto: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    client_id: int
    client: Optional[ClientInfo] = None
    nome: str
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    numero_contrato: Optional[str] = None
    numero_processo: Optional[str] = None
    modalidade_licitacao: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_previsao_fim: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    valor_contrato: Optional[Decimal] = None
    status: str
    responsavel_tecnico: Optional[str] = None
    responsavel_cliente: Optional[str] = None
    observacoes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_cotacoes: int = 0

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    per_page: int


# Endpoints
@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lista todos os projetos com paginação e filtros"""
    query = db.query(Project)

    if search:
        query = query.filter(
            Project.nome.ilike(f"%{search}%") |
            Project.codigo.ilike(f"%{search}%") |
            Project.numero_contrato.ilike(f"%{search}%")
        )

    if client_id:
        query = query.filter(Project.client_id == client_id)

    if status:
        query = query.filter(Project.status == status)

    total = query.count()

    projects = query.order_by(Project.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for project in projects:
        client_info = None
        if project.client:
            client_info = ClientInfo(
                id=project.client.id,
                nome=project.client.nome,
                nome_curto=project.client.nome_curto
            )

        items.append(ProjectResponse(
            id=project.id,
            client_id=project.client_id,
            client=client_info,
            nome=project.nome,
            codigo=project.codigo,
            descricao=project.descricao,
            numero_contrato=project.numero_contrato,
            numero_processo=project.numero_processo,
            modalidade_licitacao=project.modalidade_licitacao,
            data_inicio=project.data_inicio,
            data_previsao_fim=project.data_previsao_fim,
            data_fim=project.data_fim,
            valor_contrato=project.valor_contrato,
            status=project.status.value,
            responsavel_tecnico=project.responsavel_tecnico,
            responsavel_cliente=project.responsavel_cliente,
            observacoes=project.observacoes,
            created_at=project.created_at,
            updated_at=project.updated_at,
            total_cotacoes=len(project.cotacoes) if project.cotacoes else 0,
        ))

    return ProjectListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Obtém um projeto específico"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    client_info = None
    if project.client:
        client_info = ClientInfo(
            id=project.client.id,
            nome=project.client.nome,
            nome_curto=project.client.nome_curto
        )

    return ProjectResponse(
        id=project.id,
        client_id=project.client_id,
        client=client_info,
        nome=project.nome,
        codigo=project.codigo,
        descricao=project.descricao,
        numero_contrato=project.numero_contrato,
        numero_processo=project.numero_processo,
        modalidade_licitacao=project.modalidade_licitacao,
        data_inicio=project.data_inicio,
        data_previsao_fim=project.data_previsao_fim,
        data_fim=project.data_fim,
        valor_contrato=project.valor_contrato,
        status=project.status.value,
        responsavel_tecnico=project.responsavel_tecnico,
        responsavel_cliente=project.responsavel_cliente,
        observacoes=project.observacoes,
        created_at=project.created_at,
        updated_at=project.updated_at,
        total_cotacoes=len(project.cotacoes) if project.cotacoes else 0,
    )


@router.post("", response_model=ProjectResponse)
def create_project(project_data: ProjectCreate, db: Session = Depends(get_db)):
    """Cria um novo projeto"""
    # Verificar se o cliente existe
    client = db.query(Client).filter(Client.id == project_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Verificar código duplicado
    if project_data.codigo:
        existing = db.query(Project).filter(Project.codigo == project_data.codigo).first()
        if existing:
            raise HTTPException(status_code=400, detail="Código de projeto já existe")

    project = Project(**project_data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)

    client_info = ClientInfo(
        id=client.id,
        nome=client.nome,
        nome_curto=client.nome_curto
    )

    return ProjectResponse(
        id=project.id,
        client_id=project.client_id,
        client=client_info,
        nome=project.nome,
        codigo=project.codigo,
        descricao=project.descricao,
        numero_contrato=project.numero_contrato,
        numero_processo=project.numero_processo,
        modalidade_licitacao=project.modalidade_licitacao,
        data_inicio=project.data_inicio,
        data_previsao_fim=project.data_previsao_fim,
        data_fim=project.data_fim,
        valor_contrato=project.valor_contrato,
        status=project.status.value,
        responsavel_tecnico=project.responsavel_tecnico,
        responsavel_cliente=project.responsavel_cliente,
        observacoes=project.observacoes,
        created_at=project.created_at,
        updated_at=project.updated_at,
        total_cotacoes=0,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project_data: ProjectUpdate, db: Session = Depends(get_db)):
    """Atualiza um projeto existente"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    # Verificar cliente se estiver alterando
    if project_data.client_id and project_data.client_id != project.client_id:
        client = db.query(Client).filter(Client.id == project_data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Verificar código duplicado
    if project_data.codigo and project_data.codigo != project.codigo:
        existing = db.query(Project).filter(Project.codigo == project_data.codigo).first()
        if existing:
            raise HTTPException(status_code=400, detail="Código de projeto já existe")

    update_data = project_data.model_dump(exclude_unset=True)

    # Converter status string para enum
    if "status" in update_data:
        update_data["status"] = ProjectStatus(update_data["status"])

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    client_info = None
    if project.client:
        client_info = ClientInfo(
            id=project.client.id,
            nome=project.client.nome,
            nome_curto=project.client.nome_curto
        )

    return ProjectResponse(
        id=project.id,
        client_id=project.client_id,
        client=client_info,
        nome=project.nome,
        codigo=project.codigo,
        descricao=project.descricao,
        numero_contrato=project.numero_contrato,
        numero_processo=project.numero_processo,
        modalidade_licitacao=project.modalidade_licitacao,
        data_inicio=project.data_inicio,
        data_previsao_fim=project.data_previsao_fim,
        data_fim=project.data_fim,
        valor_contrato=project.valor_contrato,
        status=project.status.value,
        responsavel_tecnico=project.responsavel_tecnico,
        responsavel_cliente=project.responsavel_cliente,
        observacoes=project.observacoes,
        created_at=project.created_at,
        updated_at=project.updated_at,
        total_cotacoes=len(project.cotacoes) if project.cotacoes else 0,
    )


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Remove um projeto"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    # Verificar se tem cotações
    if project.cotacoes:
        raise HTTPException(
            status_code=400,
            detail=f"Projeto possui {len(project.cotacoes)} cotação(ões) vinculada(s). Remova as cotações primeiro."
        )

    db.delete(project)
    db.commit()

    return {"message": "Projeto removido com sucesso"}


@router.get("/options/list")
def get_project_options(client_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Retorna lista simplificada de projetos para select/dropdown"""
    query = db.query(Project).filter(Project.status.notin_(["CONCLUIDO", "CANCELADO"]))

    if client_id:
        query = query.filter(Project.client_id == client_id)

    projects = query.order_by(Project.nome).all()
    return [{"id": p.id, "nome": p.nome, "codigo": p.codigo, "client_id": p.client_id} for p in projects]


@router.get("/status/options")
def get_status_options():
    """Retorna lista de status possíveis"""
    return [
        {"value": "PLANEJAMENTO", "label": "Planejamento"},
        {"value": "EM_ANDAMENTO", "label": "Em Andamento"},
        {"value": "CONCLUIDO", "label": "Concluído"},
        {"value": "CANCELADO", "label": "Cancelado"},
        {"value": "SUSPENSO", "label": "Suspenso"},
    ]
