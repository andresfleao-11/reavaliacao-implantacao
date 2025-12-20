"""
API para gerenciamento de Sessões de Inventário
CRUD de sessões, carregamento de bens esperados e registro de leituras
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import pandas as pd
import io
import uuid
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import (
    User,
    Project,
    InventorySession,
    InventorySessionStatus,
    InventoryExpectedAsset,
    InventoryReadAsset,
    InventorySyncLog,
    AssetCategory,
    ReadMethod,
    PhysicalCondition,
    ExternalSystem,
    InventoryMasterUG,
    InventoryMasterUL,
    InventoryMasterUA,
    InventoryMasterPhysicalStatus,
)
from app.services.external_system_sync import ExternalSystemSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory/sessions", tags=["inventory-sessions"])


# ===== Schemas =====

class SessionCreate(BaseModel):
    project_id: int
    name: str
    description: Optional[str] = None
    ug_id: Optional[int] = None
    ul_id: Optional[int] = None
    ua_id: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    ug_id: Optional[int] = None
    ul_id: Optional[int] = None
    ua_id: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


class AssetReading(BaseModel):
    """Registro de leitura de um bem"""
    identifier: str = Field(..., description="Código RFID, código de barras ou número de tombamento")
    read_method: str = Field(default="rfid", description="rfid, barcode, manual, camera")
    physical_condition: Optional[str] = Field(None, description="good, regular, bad, unserviceable")
    physical_status_id: Optional[int] = None
    location_notes: Optional[str] = None
    observations: Optional[str] = None
    photo_file_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    characteristics: Optional[dict] = None


class BulkAssetReading(BaseModel):
    """Leituras em lote (ex: RFID múltiplas tags)"""
    readings: List[AssetReading]


class AssetCategoryUpdate(BaseModel):
    """Atualização de categoria de um bem"""
    category: str = Field(..., description="found, not_found, unregistered, written_off")
    notes: Optional[str] = None


class ExpectedAssetCreate(BaseModel):
    """Criação manual de bem esperado"""
    asset_code: str
    description: str
    rfid_code: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    expected_ul_code: Optional[str] = None
    expected_ua_code: Optional[str] = None
    extra_data: Optional[dict] = None


# ===== Helpers =====

def generate_session_code() -> str:
    """Gera código único para sessão: INV-YYYYMMDD-XXXX"""
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:4].upper()
    return f"INV-{date_part}-{random_part}"


def calculate_session_statistics(db: Session, session_id: int) -> dict:
    """Calcula estatísticas da sessão"""
    # Total esperado
    total_expected = db.query(func.count(InventoryExpectedAsset.id)).filter(
        InventoryExpectedAsset.session_id == session_id
    ).scalar() or 0

    # Contagem por categoria
    category_counts = db.query(
        InventoryReadAsset.category,
        func.count(InventoryReadAsset.id)
    ).filter(
        InventoryReadAsset.session_id == session_id
    ).group_by(InventoryReadAsset.category).all()

    stats = {
        "total_expected": total_expected,
        "total_found": 0,
        "total_not_found": 0,
        "total_unregistered": 0,
        "total_written_off": 0,
        "completion_percentage": 0.0
    }

    for category, count in category_counts:
        if category == AssetCategory.FOUND.value:
            stats["total_found"] = count
        elif category == AssetCategory.NOT_FOUND.value:
            stats["total_not_found"] = count
        elif category == AssetCategory.UNREGISTERED.value:
            stats["total_unregistered"] = count
        elif category == AssetCategory.WRITTEN_OFF.value:
            stats["total_written_off"] = count

    # Calcular percentual de conclusão
    if total_expected > 0:
        verified = stats["total_found"] + stats["total_not_found"] + stats["total_written_off"]
        stats["completion_percentage"] = round((verified / total_expected) * 100, 2)

    return stats


# ===== Session CRUD =====

@router.get("")
def list_sessions(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista sessões de inventário"""
    query = db.query(InventorySession).options(
        joinedload(InventorySession.project),
        joinedload(InventorySession.ug),
        joinedload(InventorySession.ul),
        joinedload(InventorySession.ua)
    )

    if project_id:
        query = query.filter(InventorySession.project_id == project_id)

    if status:
        query = query.filter(InventorySession.status == status)

    total = query.count()
    sessions = query.order_by(InventorySession.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for session in sessions:
        stats = calculate_session_statistics(db, session.id)
        result.append({
            "id": session.id,
            "code": session.code,
            "name": session.name,
            "description": session.description,
            "status": session.status,
            "project": {
                "id": session.project.id,
                "name": session.project.nome
            } if session.project else None,
            "ug": {"id": session.ug.id, "code": session.ug.code, "name": session.ug.name} if session.ug else None,
            "ul": {"id": session.ul.id, "code": session.ul.code, "name": session.ul.name} if session.ul else None,
            "ua": {"id": session.ua.id, "code": session.ua.code, "name": session.ua.name} if session.ua else None,
            "statistics": stats,
            "scheduled_start": session.scheduled_start,
            "scheduled_end": session.scheduled_end,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "created_at": session.created_at
        })

    return {
        "total": total,
        "items": result
    }


@router.post("")
def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cria nova sessão de inventário"""
    # Verificar projeto
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    if not project.is_inventory:
        raise HTTPException(status_code=400, detail="Projeto não está habilitado para inventário")

    # Verificar se já existe sessão em andamento para o mesmo local
    existing = db.query(InventorySession).filter(
        InventorySession.project_id == data.project_id,
        InventorySession.status.in_([
            InventorySessionStatus.DRAFT.value,
            InventorySessionStatus.IN_PROGRESS.value,
            InventorySessionStatus.PAUSED.value
        ]),
        InventorySession.ug_id == data.ug_id if data.ug_id else True,
        InventorySession.ul_id == data.ul_id if data.ul_id else True
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Já existe uma sessão em andamento para este local: {existing.code}"
        )

    session = InventorySession(
        code=generate_session_code(),
        name=data.name,
        description=data.description,
        project_id=data.project_id,
        ug_id=data.ug_id,
        ul_id=data.ul_id,
        ua_id=data.ua_id,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        created_by=current_user.id
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(f"Sessão de inventário criada: {session.code}")

    return {
        "id": session.id,
        "code": session.code,
        "name": session.name,
        "status": session.status,
        "message": "Sessão criada com sucesso"
    }


@router.get("/{session_id}")
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtém detalhes de uma sessão"""
    session = db.query(InventorySession).options(
        joinedload(InventorySession.project),
        joinedload(InventorySession.ug),
        joinedload(InventorySession.ul),
        joinedload(InventorySession.ua),
        joinedload(InventorySession.creator)
    ).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    stats = calculate_session_statistics(db, session_id)

    return {
        "id": session.id,
        "code": session.code,
        "name": session.name,
        "description": session.description,
        "status": session.status,
        "project": {
            "id": session.project.id,
            "name": session.project.nome,
            "inventory_config": session.project.inventory_config
        } if session.project else None,
        "ug": {"id": session.ug.id, "code": session.ug.code, "name": session.ug.name} if session.ug else None,
        "ul": {"id": session.ul.id, "code": session.ul.code, "name": session.ul.name} if session.ul else None,
        "ua": {"id": session.ua.id, "code": session.ua.code, "name": session.ua.name} if session.ua else None,
        "statistics": stats,
        "scheduled_start": session.scheduled_start,
        "scheduled_end": session.scheduled_end,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "created_by": {
            "id": session.creator.id,
            "name": session.creator.nome
        } if session.creator else None,
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }


@router.put("/{session_id}")
def update_session(
    session_id: int,
    data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Atualiza uma sessão"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Validar transições de status
    if data.status:
        valid_transitions = {
            InventorySessionStatus.DRAFT.value: [InventorySessionStatus.IN_PROGRESS.value, InventorySessionStatus.CANCELLED.value],
            InventorySessionStatus.IN_PROGRESS.value: [InventorySessionStatus.PAUSED.value, InventorySessionStatus.COMPLETED.value, InventorySessionStatus.CANCELLED.value],
            InventorySessionStatus.PAUSED.value: [InventorySessionStatus.IN_PROGRESS.value, InventorySessionStatus.CANCELLED.value],
            InventorySessionStatus.COMPLETED.value: [],
            InventorySessionStatus.CANCELLED.value: []
        }

        if data.status not in valid_transitions.get(session.status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Transição de status inválida: {session.status} -> {data.status}"
            )

        session.status = data.status

        # Atualizar timestamps
        if data.status == InventorySessionStatus.IN_PROGRESS.value and not session.started_at:
            session.started_at = datetime.utcnow()
        elif data.status == InventorySessionStatus.COMPLETED.value:
            session.completed_at = datetime.utcnow()

    if data.name is not None:
        session.name = data.name
    if data.description is not None:
        session.description = data.description
    if data.ug_id is not None:
        session.ug_id = data.ug_id
    if data.ul_id is not None:
        session.ul_id = data.ul_id
    if data.ua_id is not None:
        session.ua_id = data.ua_id
    if data.scheduled_start is not None:
        session.scheduled_start = data.scheduled_start
    if data.scheduled_end is not None:
        session.scheduled_end = data.scheduled_end

    db.commit()

    return {"message": "Sessão atualizada com sucesso"}


@router.delete("/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove uma sessão (apenas rascunhos)"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.DRAFT.value:
        raise HTTPException(
            status_code=400,
            detail="Apenas sessões em rascunho podem ser excluídas"
        )

    # Remover bens esperados e lidos
    db.query(InventoryReadAsset).filter(InventoryReadAsset.session_id == session_id).delete()
    db.query(InventoryExpectedAsset).filter(InventoryExpectedAsset.session_id == session_id).delete()
    db.delete(session)
    db.commit()

    return {"message": "Sessão excluída com sucesso"}


# ===== Status Actions =====

@router.post("/{session_id}/start")
def start_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Inicia uma sessão de inventário"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status not in [InventorySessionStatus.DRAFT.value, InventorySessionStatus.PAUSED.value]:
        raise HTTPException(status_code=400, detail="Sessão não pode ser iniciada")

    # Verificar se há bens esperados
    expected_count = db.query(func.count(InventoryExpectedAsset.id)).filter(
        InventoryExpectedAsset.session_id == session_id
    ).scalar()

    if expected_count == 0:
        raise HTTPException(
            status_code=400,
            detail="É necessário carregar os bens esperados antes de iniciar"
        )

    session.status = InventorySessionStatus.IN_PROGRESS.value
    if not session.started_at:
        session.started_at = datetime.utcnow()

    db.commit()

    return {"message": "Sessão iniciada com sucesso", "started_at": session.started_at}


@router.post("/{session_id}/pause")
def pause_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Pausa uma sessão em andamento"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=400, detail="Apenas sessões em andamento podem ser pausadas")

    session.status = InventorySessionStatus.PAUSED.value
    db.commit()

    return {"message": "Sessão pausada com sucesso"}


@router.post("/{session_id}/complete")
def complete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Finaliza uma sessão de inventário"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=400, detail="Apenas sessões em andamento podem ser finalizadas")

    # Marcar bens não verificados como "não encontrados"
    unverified = db.query(InventoryExpectedAsset).filter(
        InventoryExpectedAsset.session_id == session_id,
        ~InventoryExpectedAsset.id.in_(
            db.query(InventoryReadAsset.expected_asset_id).filter(
                InventoryReadAsset.session_id == session_id,
                InventoryReadAsset.expected_asset_id.isnot(None)
            )
        )
    ).all()

    for expected in unverified:
        read_asset = InventoryReadAsset(
            session_id=session_id,
            expected_asset_id=expected.id,
            asset_code=expected.asset_code,
            category=AssetCategory.NOT_FOUND.value,
            read_method=ReadMethod.MANUAL.value,
            read_at=datetime.utcnow()
        )
        db.add(read_asset)

    session.status = InventorySessionStatus.COMPLETED.value
    session.completed_at = datetime.utcnow()

    # Atualizar estatísticas finais
    stats = calculate_session_statistics(db, session_id)
    session.total_expected = stats["total_expected"]
    session.total_found = stats["total_found"]
    session.total_not_found = stats["total_not_found"]
    session.total_unregistered = stats["total_unregistered"]
    session.total_written_off = stats["total_written_off"]

    db.commit()

    return {
        "message": "Sessão finalizada com sucesso",
        "statistics": stats,
        "completed_at": session.completed_at
    }


# ===== Expected Assets =====

@router.get("/{session_id}/expected")
def list_expected_assets(
    session_id: int,
    search: Optional[str] = None,
    verified: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista bens esperados de uma sessão"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    query = db.query(InventoryExpectedAsset).filter(
        InventoryExpectedAsset.session_id == session_id
    )

    if search:
        search_filter = or_(
            InventoryExpectedAsset.asset_code.ilike(f"%{search}%"),
            InventoryExpectedAsset.description.ilike(f"%{search}%"),
            InventoryExpectedAsset.rfid_code.ilike(f"%{search}%"),
            InventoryExpectedAsset.barcode.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if verified is not None:
        # Subquery para bens verificados
        verified_ids = db.query(InventoryReadAsset.expected_asset_id).filter(
            InventoryReadAsset.session_id == session_id,
            InventoryReadAsset.expected_asset_id.isnot(None)
        ).subquery()

        if verified:
            query = query.filter(InventoryExpectedAsset.id.in_(verified_ids))
        else:
            query = query.filter(~InventoryExpectedAsset.id.in_(verified_ids))

    total = query.count()
    assets = query.order_by(InventoryExpectedAsset.asset_code).offset(skip).limit(limit).all()

    # Buscar leituras relacionadas
    asset_ids = [a.id for a in assets]
    readings = db.query(InventoryReadAsset).filter(
        InventoryReadAsset.expected_asset_id.in_(asset_ids)
    ).all()
    readings_map = {r.expected_asset_id: r for r in readings}

    result = []
    for asset in assets:
        reading = readings_map.get(asset.id)
        result.append({
            "id": asset.id,
            "asset_code": asset.asset_code,
            "description": asset.description,
            "rfid_code": asset.rfid_code,
            "barcode": asset.barcode,
            "category": asset.category,
            "expected_ul_code": asset.expected_ul_code,
            "expected_ua_code": asset.expected_ua_code,
            "is_written_off": asset.is_written_off,
            "extra_data": asset.extra_data,
            "verified": reading is not None,
            "reading": {
                "id": reading.id,
                "category": reading.category,
                "read_method": reading.read_method,
                "physical_condition": reading.physical_condition,
                "read_at": reading.read_at
            } if reading else None
        })

    return {
        "total": total,
        "items": result
    }


@router.post("/{session_id}/expected")
def add_expected_asset(
    session_id: int,
    data: ExpectedAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Adiciona bem esperado manualmente"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status not in [InventorySessionStatus.DRAFT.value]:
        raise HTTPException(status_code=400, detail="Bens só podem ser adicionados em sessões em rascunho")

    # Verificar duplicidade
    existing = db.query(InventoryExpectedAsset).filter(
        InventoryExpectedAsset.session_id == session_id,
        InventoryExpectedAsset.asset_code == data.asset_code
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Bem já existe nesta sessão")

    asset = InventoryExpectedAsset(
        session_id=session_id,
        asset_code=data.asset_code,
        description=data.description,
        rfid_code=data.rfid_code,
        barcode=data.barcode,
        category=data.category,
        expected_ul_code=data.expected_ul_code,
        expected_ua_code=data.expected_ua_code,
        extra_data=data.extra_data or {}
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"id": asset.id, "message": "Bem adicionado com sucesso"}


@router.post("/{session_id}/expected/upload")
async def upload_expected_assets(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Carrega bens esperados de um arquivo Excel/CSV"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="Bens só podem ser carregados em sessões em rascunho")

    # Ler arquivo
    content = await file.read()

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: {str(e)}")

    # Mapear colunas
    column_mapping = {
        'numero_tombamento': 'asset_code',
        'tombamento': 'asset_code',
        'patrimonio': 'asset_code',
        'plaqueta': 'asset_code',
        'numero': 'asset_code',
        'descricao': 'description',
        'nome': 'description',
        'rfid': 'rfid_code',
        'codigo_rfid': 'rfid_code',
        'codigo_barras': 'barcode',
        'barcode': 'barcode',
        'categoria': 'category',
        'ul': 'expected_ul_code',
        'codigo_ul': 'expected_ul_code',
        'ul_esperada': 'expected_ul_code',
        'ua': 'expected_ua_code',
        'codigo_ua': 'expected_ua_code',
        'ua_esperada': 'expected_ua_code',
    }

    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns=column_mapping)

    # Validar colunas obrigatórias
    if 'asset_code' not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="Coluna obrigatória não encontrada: numero_tombamento ou tombamento"
        )

    if 'description' not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="Coluna obrigatória não encontrada: descricao ou nome"
        )

    # Processar registros
    created = 0
    updated = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            asset_code = str(row['asset_code']).strip()
            if not asset_code or asset_code == 'nan':
                continue

            existing = db.query(InventoryExpectedAsset).filter(
                InventoryExpectedAsset.session_id == session_id,
                InventoryExpectedAsset.asset_code == asset_code
            ).first()

            if existing:
                existing.description = str(row.get('description', '')).strip() or existing.description
                existing.rfid_code = str(row.get('rfid_code', '')).strip() or existing.rfid_code
                existing.barcode = str(row.get('barcode', '')).strip() or existing.barcode
                updated += 1
            else:
                asset = InventoryExpectedAsset(
                    session_id=session_id,
                    asset_code=asset_code,
                    description=str(row.get('description', '')).strip(),
                    rfid_code=str(row.get('rfid_code', '')).strip() if pd.notna(row.get('rfid_code')) else None,
                    barcode=str(row.get('barcode', '')).strip() if pd.notna(row.get('barcode')) else None,
                    category=str(row.get('category', '')).strip() if pd.notna(row.get('category')) else None,
                    expected_ul_code=str(row.get('expected_ul_code', '')).strip() if pd.notna(row.get('expected_ul_code')) else None,
                    expected_ua_code=str(row.get('expected_ua_code', '')).strip() if pd.notna(row.get('expected_ua_code')) else None
                )
                db.add(asset)
                created += 1

        except Exception as e:
            errors.append(f"Linha {idx + 2}: {str(e)}")

    db.commit()

    return {
        "message": "Importação concluída",
        "created": created,
        "updated": updated,
        "errors": errors[:10] if errors else []
    }


class SyncOptions(BaseModel):
    """Opções de sincronização"""
    limit: int = 5000
    clear_existing: bool = False  # Se True, remove bens existentes antes de sincronizar


@router.post("/{session_id}/expected/sync")
async def sync_expected_assets(
    session_id: int,
    options: Optional[SyncOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sincroniza bens esperados do sistema externo (ASI).

    Baixa a carga de bens do servidor ASI usando o código da sessão e o código da UL.
    Os bens são mapeados e inseridos na tabela inventory_expected_assets.
    """
    if options is None:
        options = SyncOptions()

    session = db.query(InventorySession).options(
        joinedload(InventorySession.project),
        joinedload(InventorySession.ul)
    ).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status not in [InventorySessionStatus.DRAFT.value, InventorySessionStatus.PAUSED.value]:
        raise HTTPException(status_code=400, detail="Bens só podem ser sincronizados em sessões em rascunho ou pausadas")

    # Obter sistema externo do projeto ou o padrão
    external_system_id = None
    if session.project:
        external_system_id = session.project.external_system_id

    if not external_system_id:
        # Tentar obter sistema padrão
        system = db.query(ExternalSystem).filter(
            ExternalSystem.is_active == True,
            ExternalSystem.is_default == True
        ).first()
    else:
        system = db.query(ExternalSystem).filter(ExternalSystem.id == external_system_id).first()

    if not system:
        raise HTTPException(status_code=400, detail="Nenhum sistema externo configurado. Configure um sistema em Configurações > Sistemas Externos.")

    # Inicializar serviço de sincronização
    sync_service = ExternalSystemSyncService(db, system)

    try:
        # Baixar bens do sistema externo
        result = await sync_service.download_assets_for_session(
            session_code=session.code,
            ul_code=session.ul.code if session.ul else None,
            ug_code=session.ug.code if session.ug else None,
            limit=options.limit
        )

        if not result["success"]:
            raise HTTPException(
                status_code=502,
                detail=f"Falha ao baixar bens do servidor: {result.get('error', 'Erro desconhecido')}"
            )

        # Se solicitado, limpar bens existentes
        if options.clear_existing:
            db.query(InventoryExpectedAsset).filter(
                InventoryExpectedAsset.session_id == session_id
            ).delete()
            db.commit()

        # Inserir/atualizar bens
        created = 0
        updated = 0
        failed = 0
        errors = []

        for item in result["items"]:
            try:
                # Verificar se já existe
                existing = db.query(InventoryExpectedAsset).filter(
                    InventoryExpectedAsset.session_id == session_id,
                    InventoryExpectedAsset.asset_code == item["asset_code"]
                ).first()

                if existing:
                    # Atualizar
                    existing.asset_sequence = item.get("asset_sequence")
                    existing.description = item.get("description")
                    existing.rfid_code = item.get("rfid_code")
                    existing.barcode = item.get("barcode")
                    existing.expected_ul_code = item.get("expected_ul_code")
                    existing.expected_ua_code = item.get("expected_ua_code")
                    existing.category = item.get("category")
                    existing.is_written_off = item.get("is_written_off", False)
                    existing.extra_data = item.get("extra_data")
                    updated += 1
                else:
                    # Criar novo
                    expected_asset = InventoryExpectedAsset(
                        session_id=session_id,
                        asset_code=item["asset_code"],
                        asset_sequence=item.get("asset_sequence"),
                        description=item.get("description"),
                        rfid_code=item.get("rfid_code"),
                        barcode=item.get("barcode"),
                        expected_ul_code=item.get("expected_ul_code"),
                        expected_ua_code=item.get("expected_ua_code"),
                        category=item.get("category"),
                        is_written_off=item.get("is_written_off", False),
                        extra_data=item.get("extra_data")
                    )
                    db.add(expected_asset)
                    created += 1

            except Exception as e:
                failed += 1
                errors.append(f"Erro ao processar bem {item.get('asset_code')}: {str(e)}")
                if len(errors) > 10:
                    errors.append(f"... e mais {len(result['items']) - failed} erros")
                    break

        db.commit()

        # Atualizar estatísticas da sessão
        total_expected = db.query(func.count(InventoryExpectedAsset.id)).filter(
            InventoryExpectedAsset.session_id == session_id
        ).scalar()

        return {
            "success": True,
            "message": f"Sincronização concluída com sucesso",
            "system": system.name,
            "statistics": {
                "received": result["total_received"],
                "mapped": result["total_mapped"],
                "created": created,
                "updated": updated,
                "failed": failed,
                "total_expected": total_expected
            },
            "errors": errors if errors else None
        }

    except HTTPException:
        raise
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar ao servidor: {str(e)}")
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=f"Falha na autenticação: {str(e)}")
    except Exception as e:
        logger.error(f"Erro na sincronização: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno durante sincronização: {str(e)}")


class UploadOptions(BaseModel):
    """Opções de upload para sistema externo"""
    include_photos: bool = False


@router.post("/{session_id}/upload")
async def upload_results(
    session_id: int,
    options: Optional[UploadOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Envia resultados do inventário para o sistema externo (ASI).

    Só pode ser executado em sessões concluídas.
    """
    if options is None:
        options = UploadOptions()

    session = db.query(InventorySession).options(
        joinedload(InventorySession.project),
        joinedload(InventorySession.ul),
        joinedload(InventorySession.ug)
    ).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Só é possível enviar resultados de sessões concluídas")

    # Obter sistema externo do projeto ou o padrão
    external_system_id = None
    if session.project:
        external_system_id = session.project.external_system_id

    if not external_system_id:
        # Tentar obter sistema padrão
        system = db.query(ExternalSystem).filter(
            ExternalSystem.is_active == True,
            ExternalSystem.is_default == True
        ).first()
    else:
        system = db.query(ExternalSystem).filter(ExternalSystem.id == external_system_id).first()

    if not system:
        raise HTTPException(status_code=400, detail="Nenhum sistema externo configurado. Configure um sistema em Configurações > Sistemas Externos.")

    # Inicializar serviço de sincronização
    sync_service = ExternalSystemSyncService(db, system)

    try:
        # Enviar resultados para o sistema externo
        result = await sync_service.upload_inventory_results(
            session=session,
            include_photos=options.include_photos,
            user_login=current_user.username if current_user else "sistema"
        )

        if not result["success"]:
            raise HTTPException(
                status_code=502,
                detail=f"Falha ao enviar resultados: {result.get('error', 'Erro desconhecido')}"
            )

        # Atualizar sessão com informações de envio
        session.external_transmission_number = result.get("transmission_number")
        session.external_inventory_id = result.get("inventory_id")
        session.external_uploaded_at = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "message": "Resultados enviados com sucesso",
            "system": system.name,
            "transmission_number": result.get("transmission_number"),
            "inventory_id": result.get("inventory_id"),
            "items_sent": result.get("items_sent", 0)
        }

    except HTTPException:
        raise
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar ao servidor: {str(e)}")
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=f"Falha na autenticação: {str(e)}")
    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno durante envio: {str(e)}")


# ===== Asset Readings =====

@router.get("/{session_id}/readings")
def list_readings(
    session_id: int,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista leituras de uma sessão"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    query = db.query(InventoryReadAsset).options(
        joinedload(InventoryReadAsset.expected_asset)
    ).filter(InventoryReadAsset.session_id == session_id)

    if category:
        query = query.filter(InventoryReadAsset.category == category)

    total = query.count()
    readings = query.order_by(InventoryReadAsset.read_at.desc()).offset(skip).limit(limit).all()

    result = []
    for reading in readings:
        result.append({
            "id": reading.id,
            "asset_code": reading.asset_code,
            "rfid_code": reading.rfid_code,
            "barcode": reading.barcode,
            "category": reading.category,
            "read_method": reading.read_method,
            "physical_condition": reading.physical_condition,
            "notes": reading.notes,
            "read_latitude": reading.read_latitude,
            "read_longitude": reading.read_longitude,
            "read_at": reading.read_at,
            "expected_asset": {
                "id": reading.expected_asset.id,
                "description": reading.expected_asset.description,
                "rfid_code": reading.expected_asset.rfid_code
            } if reading.expected_asset else None
        })

    return {
        "total": total,
        "items": result
    }


@router.post("/{session_id}/readings")
def register_reading(
    session_id: int,
    data: AssetReading,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Registra leitura de um bem"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=400, detail="Sessão não está em andamento")

    # Buscar bem esperado pelo identificador
    expected = None
    identifier = data.identifier.strip()

    # Tentar encontrar por RFID, código de barras ou número de tombamento
    expected = db.query(InventoryExpectedAsset).filter(
        InventoryExpectedAsset.session_id == session_id,
        or_(
            InventoryExpectedAsset.rfid_code == identifier,
            InventoryExpectedAsset.barcode == identifier,
            InventoryExpectedAsset.asset_code == identifier
        )
    ).first()

    # Verificar se já foi lido
    if expected:
        existing_reading = db.query(InventoryReadAsset).filter(
            InventoryReadAsset.session_id == session_id,
            InventoryReadAsset.expected_asset_id == expected.id
        ).first()

        if existing_reading:
            # Atualizar leitura existente
            existing_reading.read_method = data.read_method
            existing_reading.physical_condition = data.physical_condition
            existing_reading.physical_condition_code = str(data.physical_status_id) if data.physical_status_id else None
            existing_reading.notes = data.observations
            existing_reading.photo_file_id = str(data.photo_file_id) if data.photo_file_id else None
            existing_reading.read_latitude = data.latitude
            existing_reading.read_longitude = data.longitude
            existing_reading.read_at = datetime.utcnow()

            db.commit()

            return {
                "id": existing_reading.id,
                "category": existing_reading.category,
                "message": "Leitura atualizada",
                "expected_asset": {
                    "id": expected.id,
                    "description": expected.description
                }
            }

    # Determinar categoria
    if expected:
        category = AssetCategory.FOUND.value
        asset_code = expected.asset_code
    else:
        category = AssetCategory.UNREGISTERED.value
        asset_code = identifier

    # Criar leitura
    reading = InventoryReadAsset(
        session_id=session_id,
        expected_asset_id=expected.id if expected else None,
        asset_code=asset_code,
        category=category,
        read_method=data.read_method,
        physical_condition=data.physical_condition,
        physical_condition_code=str(data.physical_status_id) if data.physical_status_id else None,
        notes=data.observations,
        photo_file_id=str(data.photo_file_id) if data.photo_file_id else None,
        read_latitude=data.latitude,
        read_longitude=data.longitude,
        read_at=datetime.utcnow()
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    return {
        "id": reading.id,
        "category": category,
        "message": "Leitura registrada",
        "expected_asset": {
            "id": expected.id,
            "description": expected.description
        } if expected else None
    }


@router.post("/{session_id}/readings/bulk")
def register_bulk_readings(
    session_id: int,
    data: BulkAssetReading,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Registra múltiplas leituras de uma vez (RFID bulk)"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=400, detail="Sessão não está em andamento")

    results = {
        "found": 0,
        "unregistered": 0,
        "updated": 0,
        "errors": []
    }

    for reading_data in data.readings:
        try:
            identifier = reading_data.identifier.strip()

            # Buscar bem esperado
            expected = db.query(InventoryExpectedAsset).filter(
                InventoryExpectedAsset.session_id == session_id,
                or_(
                    InventoryExpectedAsset.rfid_code == identifier,
                    InventoryExpectedAsset.barcode == identifier,
                    InventoryExpectedAsset.asset_code == identifier
                )
            ).first()

            # Verificar leitura existente
            if expected:
                existing = db.query(InventoryReadAsset).filter(
                    InventoryReadAsset.session_id == session_id,
                    InventoryReadAsset.expected_asset_id == expected.id
                ).first()

                if existing:
                    existing.read_at = datetime.utcnow()
                    results["updated"] += 1
                    continue

            # Criar nova leitura
            category = AssetCategory.FOUND.value if expected else AssetCategory.UNREGISTERED.value

            reading = InventoryReadAsset(
                session_id=session_id,
                expected_asset_id=expected.id if expected else None,
                asset_code=expected.asset_code if expected else identifier,
                category=category,
                read_method=reading_data.read_method,
                read_at=datetime.utcnow()
            )

            db.add(reading)

            if expected:
                results["found"] += 1
            else:
                results["unregistered"] += 1

        except Exception as e:
            results["errors"].append(f"{identifier}: {str(e)}")

    db.commit()

    return results


@router.put("/{session_id}/readings/{reading_id}/category")
def update_reading_category(
    session_id: int,
    reading_id: int,
    data: AssetCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Atualiza categoria de um bem (ex: marcar como baixado)"""
    reading = db.query(InventoryReadAsset).filter(
        InventoryReadAsset.id == reading_id,
        InventoryReadAsset.session_id == session_id
    ).first()

    if not reading:
        raise HTTPException(status_code=404, detail="Leitura não encontrada")

    # Validar categoria
    valid_categories = [c.value for c in AssetCategory]
    if data.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Categoria inválida. Valores válidos: {valid_categories}"
        )

    reading.category = data.category
    if data.notes:
        reading.observations = data.notes

    db.commit()

    return {"message": "Categoria atualizada com sucesso"}


# ===== Statistics =====

@router.get("/{session_id}/statistics")
def get_session_statistics(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtém estatísticas detalhadas da sessão"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    stats = calculate_session_statistics(db, session_id)

    # Estatísticas por método de leitura
    by_method = db.query(
        InventoryReadAsset.read_method,
        func.count(InventoryReadAsset.id)
    ).filter(
        InventoryReadAsset.session_id == session_id
    ).group_by(InventoryReadAsset.read_method).all()

    stats["by_method"] = {method: count for method, count in by_method}

    # Estatísticas por condição física
    by_condition = db.query(
        InventoryReadAsset.physical_condition,
        func.count(InventoryReadAsset.id)
    ).filter(
        InventoryReadAsset.session_id == session_id,
        InventoryReadAsset.physical_condition.isnot(None)
    ).group_by(InventoryReadAsset.physical_condition).all()

    stats["by_condition"] = {condition: count for condition, count in by_condition}

    return stats


# ===== Mobile App Endpoints (sem JWT) =====

class MobileActiveSessionResponse(BaseModel):
    """Resposta para o app verificar sessões de inventário ativas"""
    has_active_session: bool
    sessions: List[dict] = []


class MobileReadingCreate(BaseModel):
    """Leitura enviada pelo app mobile"""
    identifier: str
    read_method: str = "rfid"
    rssi: Optional[str] = None
    device_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class MobileBulkReadings(BaseModel):
    """Múltiplas leituras do app mobile"""
    readings: List[MobileReadingCreate]


@router.get("/app/active", response_model=MobileActiveSessionResponse)
def get_active_sessions_for_app(
    user_id: int = Query(..., description="ID do usuário"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para o app mobile verificar sessões de inventário ativas.
    Não requer autenticação JWT - usa user_id como parâmetro.
    Retorna todas as sessões em andamento que o usuário pode acessar.
    """
    # Buscar sessões em andamento
    sessions = db.query(InventorySession).options(
        joinedload(InventorySession.project),
        joinedload(InventorySession.ug),
        joinedload(InventorySession.ul)
    ).filter(
        InventorySession.status == InventorySessionStatus.IN_PROGRESS.value
    ).order_by(InventorySession.started_at.desc()).all()

    if not sessions:
        return MobileActiveSessionResponse(has_active_session=False, sessions=[])

    result = []
    for session in sessions:
        stats = calculate_session_statistics(db, session.id)
        result.append({
            "id": session.id,
            "code": session.code,
            "name": session.name,
            "project_name": session.project.nome if session.project else None,
            "ug_name": session.ug.name if session.ug else None,
            "ul_name": session.ul.name if session.ul else None,
            "total_expected": stats["total_expected"],
            "total_found": stats["total_found"],
            "completion_percentage": stats["completion_percentage"],
            "started_at": session.started_at.isoformat() if session.started_at else None
        })

    return MobileActiveSessionResponse(has_active_session=True, sessions=result)


@router.post("/app/{session_id}/readings", response_model=dict)
def add_readings_from_mobile_app(
    session_id: int,
    data: MobileBulkReadings,
    user_id: int = Query(..., description="ID do usuário"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para o app mobile enviar leituras RFID para uma sessão de inventário.
    Não requer autenticação JWT - usa user_id como parâmetro.

    Processa cada leitura e tenta fazer matching com bens esperados por:
    - Código RFID
    - Código de barras
    - Número de tombamento
    """
    session = db.query(InventorySession).filter(
        InventorySession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != InventorySessionStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=400, detail="Sessão não está em andamento")

    results = {
        "success": True,
        "found": 0,
        "unregistered": 0,
        "updated": 0,
        "total_processed": 0,
        "details": []
    }

    for reading_data in data.readings:
        identifier = reading_data.identifier.strip()
        if not identifier:
            continue

        results["total_processed"] += 1

        # Buscar bem esperado por RFID, barcode ou tombamento
        expected = db.query(InventoryExpectedAsset).filter(
            InventoryExpectedAsset.session_id == session_id,
            or_(
                InventoryExpectedAsset.rfid_code == identifier,
                InventoryExpectedAsset.barcode == identifier,
                InventoryExpectedAsset.asset_code == identifier
            )
        ).first()

        # Verificar se já existe leitura
        if expected:
            existing = db.query(InventoryReadAsset).filter(
                InventoryReadAsset.session_id == session_id,
                InventoryReadAsset.expected_asset_id == expected.id
            ).first()

            if existing:
                # Atualizar timestamp da leitura existente
                existing.read_at = datetime.utcnow()
                existing.rfid_code = identifier if reading_data.read_method == "rfid" else existing.rfid_code
                results["updated"] += 1
                results["details"].append({
                    "identifier": identifier,
                    "status": "updated",
                    "asset_code": expected.asset_code,
                    "description": expected.description[:50] if expected.description else None
                })
                continue

        # Verificar se já existe leitura por identificador (para não cadastrados)
        if not expected:
            existing_unreg = db.query(InventoryReadAsset).filter(
                InventoryReadAsset.session_id == session_id,
                or_(
                    InventoryReadAsset.rfid_code == identifier,
                    InventoryReadAsset.asset_code == identifier
                )
            ).first()

            if existing_unreg:
                existing_unreg.read_at = datetime.utcnow()
                results["updated"] += 1
                results["details"].append({
                    "identifier": identifier,
                    "status": "updated",
                    "asset_code": existing_unreg.asset_code,
                    "description": None
                })
                continue

        # Criar nova leitura
        category = AssetCategory.FOUND.value if expected else AssetCategory.UNREGISTERED.value

        reading = InventoryReadAsset(
            session_id=session_id,
            expected_asset_id=expected.id if expected else None,
            asset_code=expected.asset_code if expected else identifier,
            rfid_code=identifier if reading_data.read_method == "rfid" else None,
            barcode=identifier if reading_data.read_method == "barcode" else None,
            category=category,
            read_method=reading_data.read_method,
            read_latitude=reading_data.latitude,
            read_longitude=reading_data.longitude,
            read_at=datetime.utcnow()
        )
        db.add(reading)

        if expected:
            results["found"] += 1
            results["details"].append({
                "identifier": identifier,
                "status": "found",
                "asset_code": expected.asset_code,
                "description": expected.description[:50] if expected.description else None
            })
        else:
            results["unregistered"] += 1
            results["details"].append({
                "identifier": identifier,
                "status": "unregistered",
                "asset_code": identifier,
                "description": None
            })

    db.commit()

    # Calcular estatísticas atualizadas
    stats = calculate_session_statistics(db, session_id)
    results["session_stats"] = stats

    return results


@router.get("/app/{session_id}/status")
def get_session_status_for_app(
    session_id: int,
    user_id: int = Query(..., description="ID do usuário"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para o app mobile obter status atual de uma sessão.
    Retorna estatísticas e últimas leituras.
    """
    session = db.query(InventorySession).options(
        joinedload(InventorySession.project)
    ).filter(InventorySession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    stats = calculate_session_statistics(db, session_id)

    # Últimas 10 leituras
    recent_readings = db.query(InventoryReadAsset).filter(
        InventoryReadAsset.session_id == session_id
    ).order_by(InventoryReadAsset.read_at.desc()).limit(10).all()

    return {
        "id": session.id,
        "code": session.code,
        "name": session.name,
        "status": session.status,
        "statistics": stats,
        "recent_readings": [
            {
                "asset_code": r.asset_code,
                "category": r.category,
                "read_method": r.read_method,
                "read_at": r.read_at.isoformat() if r.read_at else None
            }
            for r in recent_readings
        ]
    }
