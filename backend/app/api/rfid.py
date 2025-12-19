from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User, RfidTag, RfidTagBatch, Item

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rfid", tags=["RFID"])


# Schemas
class TagInput(BaseModel):
    epc: str = Field(..., description="Codigo EPC da tag RFID")
    rssi: str = Field(..., description="Intensidade do sinal")
    timestamp: str = Field(..., description="Timestamp ISO da leitura")


class TagBatchRequest(BaseModel):
    device_id: str = Field(..., description="ID do dispositivo (ex: R6-XX:XX:XX:XX:XX:XX)")
    tags: List[TagInput] = Field(..., description="Lista de tags lidas")
    batch_id: str = Field(..., description="UUID do lote")
    location: Optional[str] = Field(None, description="Local da leitura")
    project_id: Optional[int] = Field(None, description="ID do projeto vinculado")


class TagBatchResponse(BaseModel):
    success: bool
    message: str
    received_count: int
    batch_id: str


class TagResponse(BaseModel):
    id: int
    epc: str
    rssi: Optional[str]
    read_at: datetime
    matched: bool
    item_id: Optional[int]

    class Config:
        from_attributes = True


class BatchResponse(BaseModel):
    id: int
    batch_id: str
    device_id: str
    location: Optional[str]
    tag_count: int
    created_at: datetime
    tags: List[TagResponse] = []

    class Config:
        from_attributes = True


class BatchListResponse(BaseModel):
    id: int
    batch_id: str
    device_id: str
    location: Optional[str]
    tag_count: int
    created_at: datetime
    project_id: Optional[int]

    class Config:
        from_attributes = True


# Endpoints

@router.post("/tags", response_model=TagBatchResponse, summary="Receber tags RFID do middleware")
async def receive_tags(
    request: TagBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint para receber lote de tags RFID do middleware mobile.

    - **device_id**: Identificador do dispositivo (ex: R6-XX:XX:XX:XX:XX:XX)
    - **tags**: Lista de tags com EPC, RSSI e timestamp
    - **batch_id**: UUID único do lote
    - **location**: Local opcional da leitura
    - **project_id**: ID do projeto para vincular (opcional)
    """
    try:
        # Verificar se o batch_id já existe
        existing_batch = db.query(RfidTagBatch).filter(
            RfidTagBatch.batch_id == request.batch_id
        ).first()

        if existing_batch:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lote {request.batch_id} já foi processado anteriormente"
            )

        # Criar o lote
        batch = RfidTagBatch(
            batch_id=request.batch_id,
            device_id=request.device_id,
            location=request.location,
            project_id=request.project_id,
            user_id=current_user.id,
            tag_count=len(request.tags)
        )
        db.add(batch)
        db.flush()  # Para obter o ID

        # Processar cada tag
        for tag_input in request.tags:
            # Converter timestamp ISO para datetime
            try:
                read_at = datetime.fromisoformat(tag_input.timestamp.replace('Z', '+00:00'))
            except ValueError:
                read_at = datetime.utcnow()

            tag = RfidTag(
                batch_id=batch.id,
                epc=tag_input.epc,
                rssi=tag_input.rssi,
                read_at=read_at,
                matched=False
            )
            db.add(tag)

        db.commit()

        logger.info(
            f"Lote RFID recebido: {request.batch_id} com {len(request.tags)} tags",
            extra={
                'batch_id': request.batch_id,
                'device_id': request.device_id,
                'tag_count': len(request.tags),
                'user_id': current_user.id
            }
        )

        return TagBatchResponse(
            success=True,
            message=f"Lote recebido com sucesso: {len(request.tags)} tags",
            received_count=len(request.tags),
            batch_id=request.batch_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar lote RFID: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar lote: {str(e)}"
        )


@router.get("/batches", response_model=List[BatchListResponse], summary="Listar lotes de leitura RFID")
async def list_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    project_id: Optional[int] = Query(None, description="Filtrar por projeto"),
    device_id: Optional[str] = Query(None, description="Filtrar por dispositivo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Listar todos os lotes de leitura RFID"""
    query = db.query(RfidTagBatch)

    if project_id:
        query = query.filter(RfidTagBatch.project_id == project_id)

    if device_id:
        query = query.filter(RfidTagBatch.device_id.ilike(f"%{device_id}%"))

    batches = query.order_by(RfidTagBatch.created_at.desc()).offset(skip).limit(limit).all()

    return batches


@router.get("/batches/{batch_id}", response_model=BatchResponse, summary="Obter detalhes de um lote")
async def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obter detalhes de um lote específico incluindo todas as tags"""
    batch = db.query(RfidTagBatch).filter(
        RfidTagBatch.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lote {batch_id} não encontrado"
        )

    return batch


@router.get("/tags/search", response_model=List[TagResponse], summary="Buscar tag por EPC")
async def search_tag(
    epc: str = Query(..., description="Código EPC para buscar"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buscar todas as leituras de uma tag específica pelo EPC"""
    tags = db.query(RfidTag).filter(
        RfidTag.epc.ilike(f"%{epc}%")
    ).order_by(RfidTag.read_at.desc()).limit(100).all()

    return tags


@router.post("/tags/{tag_id}/match/{item_id}", summary="Vincular tag a um item do inventário")
async def match_tag_to_item(
    tag_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Vincular uma tag RFID a um item do cadastro de itens"""
    tag = db.query(RfidTag).filter(RfidTag.id == tag_id).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag não encontrada"
        )

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item não encontrado"
        )

    tag.item_id = item_id
    tag.matched = True
    db.commit()

    return {"success": True, "message": f"Tag {tag.epc} vinculada ao item {item.codigo}"}


@router.get("/stats", summary="Estatísticas de leitura RFID")
async def get_stats(
    project_id: Optional[int] = Query(None, description="Filtrar por projeto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obter estatísticas gerais de leitura RFID"""
    query_batches = db.query(RfidTagBatch)
    query_tags = db.query(RfidTag)

    if project_id:
        query_batches = query_batches.filter(RfidTagBatch.project_id == project_id)
        batch_ids = [b.id for b in query_batches.all()]
        query_tags = query_tags.filter(RfidTag.batch_id.in_(batch_ids))

    total_batches = query_batches.count()
    total_tags = query_tags.count()
    matched_tags = query_tags.filter(RfidTag.matched == True).count()
    unique_epcs = db.query(func.count(func.distinct(RfidTag.epc))).scalar()

    return {
        "total_batches": total_batches,
        "total_tags": total_tags,
        "matched_tags": matched_tags,
        "unmatched_tags": total_tags - matched_tags,
        "unique_epcs": unique_epcs
    }


@router.delete("/batches/{batch_id}", summary="Excluir lote de leitura")
async def delete_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Excluir um lote de leitura e todas as suas tags"""
    batch = db.query(RfidTagBatch).filter(
        RfidTagBatch.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lote {batch_id} não encontrado"
        )

    tag_count = batch.tag_count
    db.delete(batch)
    db.commit()

    return {"success": True, "message": f"Lote {batch_id} excluído com {tag_count} tags"}
