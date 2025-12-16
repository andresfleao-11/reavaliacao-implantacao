"""
API endpoints para cotacao em lote.
Suporta 3 metodos de entrada: texto, imagens e arquivo CSV/XLSX.
"""
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Form, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import QuoteRequest, File, User, QuoteStatus
from app.models.quote_request import QuoteInputType
from app.models.batch_quote import BatchQuoteJob, BatchJobStatus
from app.models.file import FileType
from app.models.project import Project
from app.models.project_config import ProjectConfigVersion
from app.utils.file_validation import validate_multiple_uploads, sanitize_filename, ALLOWED_IMAGE_EXTENSIONS
from app.api.schemas import (
    BatchCreateResponse,
    BatchDetailResponse,
    BatchListResponse,
    BatchListItem,
    BatchQuotesListResponse,
    BatchQuoteItem,
    ProjectInfoResponse,
)
from app.services.file_parser import BatchFileParser
from app.tasks.batch_tasks import process_batch_job
from datetime import datetime
import os
import hashlib
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch-quotes", tags=["batch-quotes"])

# Configurar limiter para batch quotes
limiter = Limiter(key_func=get_remote_address)

# Extensoes permitidas para upload de arquivo
ALLOWED_FILE_EXTENSIONS = {'.csv', '.xlsx', '.xls'}


def _get_active_config_version(db: Session, project_id: Optional[int]) -> Optional[int]:
    """Busca a versao ativa da configuracao do projeto."""
    if not project_id:
        return None
    active_config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.project_id == project_id,
        ProjectConfigVersion.ativo == True
    ).first()
    return active_config.id if active_config else None


def _calculate_progress(batch: BatchQuoteJob) -> float:
    """Calcula percentual de progresso do lote."""
    if batch.total_items == 0:
        return 0.0
    return round((batch.completed_items + batch.failed_items) / batch.total_items * 100, 1)


def _can_resume_batch(batch: BatchQuoteJob) -> bool:
    """Verifica se o lote pode ser retomado."""
    # Pode retomar se status for ERROR ou PARTIALLY_COMPLETED e houver itens pendentes ou com falha
    if batch.status not in [BatchJobStatus.ERROR, BatchJobStatus.PARTIALLY_COMPLETED]:
        return False
    pending_count = batch.total_items - batch.completed_items - batch.failed_items
    # Permite retomar se houver pendentes OU se houver falhas para retentar
    return pending_count > 0 or batch.failed_items > 0


@router.post("/text", response_model=BatchCreateResponse)
@limiter.limit("5/minute")
async def create_text_batch(
    request: Request,
    input_text: str = Form(...),
    local: Optional[str] = Form(None),
    pesquisador: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cria um lote de cotacoes a partir de texto com descricoes separadas por ponto-e-virgula.
    Exemplo: "Notebook Dell 15; Mouse Logitech; Teclado Mecanico"
    """
    try:
        descriptions = BatchFileParser.parse_text_batch(input_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    config_version_id = _get_active_config_version(db, project_id)

    # Criar o job de lote
    batch_job = BatchQuoteJob(
        status=BatchJobStatus.PENDING,
        input_type=QuoteInputType.TEXT_BATCH.value,
        project_id=project_id,
        config_version_id=config_version_id,
        local=local,
        pesquisador=pesquisador or current_user.name,
        total_items=len(descriptions),
        original_input_text=input_text,
    )
    db.add(batch_job)
    db.flush()

    # Criar as cotacoes individuais
    for idx, desc in enumerate(descriptions):
        quote = QuoteRequest(
            status=QuoteStatus.PROCESSING,
            input_type=QuoteInputType.TEXT_BATCH,
            input_text=desc,
            project_id=project_id,
            config_version_id=config_version_id,
            local=local,
            pesquisador=pesquisador or current_user.name,
            batch_job_id=batch_job.id,
            batch_index=idx,
        )
        db.add(quote)

    db.commit()

    # Disparar task de processamento
    task = process_batch_job.delay(batch_job.id)
    batch_job.celery_task_id = task.id
    db.commit()

    logger.info(f"Batch TEXT criado: {batch_job.id} com {len(descriptions)} itens")

    return BatchCreateResponse(
        batch_id=batch_job.id,
        total_items=len(descriptions),
        message=f"Lote criado com {len(descriptions)} cotacoes"
    )


@router.post("/images", response_model=BatchCreateResponse)
@limiter.limit("5/minute")
async def create_image_batch(
    request: Request,
    images: List[UploadFile] = FastAPIFile(...),
    local: Optional[str] = Form(None),
    pesquisador: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cria um lote de cotacoes a partir de imagens (uma imagem por produto).
    """
    # Filtrar imagens validas
    valid_images = [img for img in images if img.filename]

    if not valid_images:
        raise HTTPException(status_code=400, detail="Nenhuma imagem fornecida")

    try:
        BatchFileParser.validate_images_batch(len(valid_images))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validar arquivos
    image_contents = await validate_multiple_uploads(
        valid_images,
        max_files=500,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        max_size_per_file=5 * 1024 * 1024,
        max_total_size=500 * 1024 * 1024  # 500MB total para lotes
    )

    config_version_id = _get_active_config_version(db, project_id)

    # Criar o job de lote
    batch_job = BatchQuoteJob(
        status=BatchJobStatus.PENDING,
        input_type=QuoteInputType.IMAGE_BATCH.value,
        project_id=project_id,
        config_version_id=config_version_id,
        local=local,
        pesquisador=pesquisador or current_user.name,
        total_items=len(valid_images),
    )
    db.add(batch_job)
    db.flush()

    # Criar as cotacoes e salvar imagens
    for idx, (upload_file, content) in enumerate(zip(valid_images, image_contents)):
        quote = QuoteRequest(
            status=QuoteStatus.PROCESSING,
            input_type=QuoteInputType.IMAGE_BATCH,
            project_id=project_id,
            config_version_id=config_version_id,
            local=local,
            pesquisador=pesquisador or current_user.name,
            batch_job_id=batch_job.id,
            batch_index=idx,
        )
        db.add(quote)
        db.flush()

        # Salvar imagem
        safe_filename = sanitize_filename(upload_file.filename)
        file_hash = hashlib.sha256(content).hexdigest()
        storage_filename = f"{file_hash}_{safe_filename}"
        storage_path = os.path.join("storage", "uploads", storage_filename)

        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(content)

        file_record = File(
            type=FileType.INPUT_IMAGE,
            mime_type=upload_file.content_type or "image/jpeg",
            storage_path=storage_path,
            sha256=file_hash,
            quote_request_id=quote.id
        )
        db.add(file_record)

    db.commit()

    # Disparar task de processamento
    task = process_batch_job.delay(batch_job.id)
    batch_job.celery_task_id = task.id
    db.commit()

    logger.info(f"Batch IMAGE criado: {batch_job.id} com {len(valid_images)} itens")

    return BatchCreateResponse(
        batch_id=batch_job.id,
        total_items=len(valid_images),
        message=f"Lote criado com {len(valid_images)} cotacoes"
    )


@router.post("/file", response_model=BatchCreateResponse)
@limiter.limit("5/minute")
async def create_file_batch(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    local: Optional[str] = Form(None),
    pesquisador: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cria um lote de cotacoes a partir de arquivo CSV ou XLSX.
    O arquivo deve conter uma coluna com as descricoes dos produtos.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nenhum arquivo fornecido")

    # Verificar extensao
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato nao suportado: {ext}. Use CSV ou XLSX."
        )

    # Ler conteudo
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB max
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Maximo 10MB.")

    # Fazer parse do arquivo
    try:
        descriptions, col_name = BatchFileParser.parse_file(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    config_version_id = _get_active_config_version(db, project_id)

    # Salvar arquivo original
    safe_filename = sanitize_filename(file.filename)
    file_hash = hashlib.sha256(content).hexdigest()
    storage_filename = f"{file_hash}_{safe_filename}"
    storage_path = os.path.join("storage", "uploads", storage_filename)

    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    with open(storage_path, "wb") as f:
        f.write(content)

    file_record = File(
        type=FileType.INPUT_IMAGE,  # Reutilizando tipo - poderia criar FILE_BATCH
        mime_type=file.content_type or "application/octet-stream",
        storage_path=storage_path,
        sha256=file_hash,
    )
    db.add(file_record)
    db.flush()

    # Criar o job de lote
    batch_job = BatchQuoteJob(
        status=BatchJobStatus.PENDING,
        input_type=QuoteInputType.FILE_BATCH.value,
        project_id=project_id,
        config_version_id=config_version_id,
        local=local,
        pesquisador=pesquisador or current_user.name,
        total_items=len(descriptions),
        original_input_file_id=file_record.id,
    )
    db.add(batch_job)
    db.flush()

    # Criar as cotacoes individuais
    for idx, desc in enumerate(descriptions):
        quote = QuoteRequest(
            status=QuoteStatus.PROCESSING,
            input_type=QuoteInputType.FILE_BATCH,
            input_text=desc,
            project_id=project_id,
            config_version_id=config_version_id,
            local=local,
            pesquisador=pesquisador or current_user.name,
            batch_job_id=batch_job.id,
            batch_index=idx,
        )
        db.add(quote)

    db.commit()

    # Disparar task de processamento
    task = process_batch_job.delay(batch_job.id)
    batch_job.celery_task_id = task.id
    db.commit()

    logger.info(f"Batch FILE criado: {batch_job.id} com {len(descriptions)} itens da coluna '{col_name}'")

    return BatchCreateResponse(
        batch_id=batch_job.id,
        total_items=len(descriptions),
        message=f"Lote criado com {len(descriptions)} cotacoes a partir da coluna '{col_name}'"
    )


@router.get("/{batch_id}", response_model=BatchDetailResponse)
def get_batch_status(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna o status detalhado de um lote de cotacoes."""
    batch = db.query(BatchQuoteJob).options(
        joinedload(BatchQuoteJob.project)
    ).filter(BatchQuoteJob.id == batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    # Contar cotacoes por status
    status_counts = db.query(
        QuoteRequest.status,
        func.count(QuoteRequest.id)
    ).filter(
        QuoteRequest.batch_job_id == batch_id
    ).group_by(QuoteRequest.status).all()

    quotes_awaiting = 0
    quotes_done = 0
    for status, count in status_counts:
        if status == QuoteStatus.AWAITING_REVIEW:
            quotes_awaiting = count
        elif status == QuoteStatus.DONE:
            quotes_done = count

    project_info = None
    if batch.project:
        project_info = ProjectInfoResponse(
            id=batch.project.id,
            nome=batch.project.nome,
            cliente_nome=batch.project.client.nome if batch.project.client else None,
        )

    return BatchDetailResponse(
        id=batch.id,
        status=batch.status.value,
        input_type=batch.input_type,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        total_items=batch.total_items,
        completed_items=batch.completed_items,
        failed_items=batch.failed_items,
        progress_percentage=_calculate_progress(batch),
        project_id=batch.project_id,
        project=project_info,
        local=batch.local,
        pesquisador=batch.pesquisador,
        error_message=batch.error_message,
        can_resume=_can_resume_batch(batch),
        quotes_awaiting_review=quotes_awaiting,
        quotes_done=quotes_done,
    )


@router.get("/{batch_id}/quotes", response_model=BatchQuotesListResponse)
def list_batch_quotes(
    batch_id: int,
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista as cotacoes de um lote com paginacao."""
    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    query = db.query(QuoteRequest).filter(QuoteRequest.batch_job_id == batch_id)

    # Filtrar por status se especificado
    if status:
        try:
            status_enum = QuoteStatus(status)
            query = query.filter(QuoteRequest.status == status_enum)
        except ValueError:
            pass  # Status invalido, ignorar filtro

    # Ordenar por batch_index
    query = query.order_by(QuoteRequest.batch_index)

    total = query.count()
    quotes = query.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for q in quotes:
        nome_item = None
        if q.claude_payload_json and isinstance(q.claude_payload_json, dict):
            nome_item = q.claude_payload_json.get("nome_canonico") or q.claude_payload_json.get("nome")

        items.append(BatchQuoteItem(
            id=q.id,
            status=q.status.value,
            input_type=q.input_type.value if q.input_type else None,
            created_at=q.created_at,
            codigo_item=q.codigo_item,
            nome_item=nome_item,
            valor_medio=q.valor_medio,
            batch_index=q.batch_index,
            error_message=q.error_message,
        ))

    return BatchQuotesListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/{batch_id}/cancel")
def cancel_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancela um lote em processamento."""
    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    if batch.status not in [BatchJobStatus.PENDING, BatchJobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail=f"Nao e possivel cancelar lote com status {batch.status.value}"
        )

    # Atualizar status do lote
    batch.status = BatchJobStatus.CANCELLED
    batch.error_message = "Cancelado pelo usuario"

    # Cancelar cotacoes pendentes
    db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch_id,
        QuoteRequest.status == QuoteStatus.PROCESSING
    ).update({
        QuoteRequest.status: QuoteStatus.CANCELLED,
        QuoteRequest.error_message: "Lote cancelado pelo usuario"
    })

    db.commit()

    logger.info(f"Batch {batch_id} cancelado pelo usuario {current_user.email}")

    return {"message": "Lote cancelado com sucesso"}


@router.post("/{batch_id}/resume")
def resume_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retoma um lote interrompido ou com falhas."""
    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    if not _can_resume_batch(batch):
        raise HTTPException(
            status_code=400,
            detail=f"Nao e possivel retomar lote com status {batch.status.value}"
        )

    # Atualizar status do lote
    batch.status = BatchJobStatus.PROCESSING
    batch.error_message = None

    # Resetar cotacoes com erro para PROCESSING
    db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch_id,
        QuoteRequest.status == QuoteStatus.ERROR
    ).update({
        QuoteRequest.status: QuoteStatus.PROCESSING,
        QuoteRequest.error_message: None
    })

    db.commit()

    # Disparar task de processamento (continua de onde parou)
    task = process_batch_job.delay(batch_id, resume=True)
    batch.celery_task_id = task.id
    db.commit()

    logger.info(f"Batch {batch_id} retomado pelo usuario {current_user.email}")

    return {"message": "Lote retomado com sucesso"}


@router.get("", response_model=BatchListResponse)
def list_batches(
    page: int = 1,
    per_page: int = 20,
    batch_id: Optional[int] = None,
    project_id: Optional[int] = None,
    client_id: Optional[int] = None,
    input_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista todos os lotes com paginacao otimizada."""
    # Query base com joinedload para evitar N+1
    query = db.query(BatchQuoteJob).options(
        joinedload(BatchQuoteJob.project).joinedload(Project.client)
    )

    # Filtrar por ID do lote
    if batch_id:
        query = query.filter(BatchQuoteJob.id == batch_id)

    # Filtrar por projeto se especificado
    if project_id:
        query = query.filter(BatchQuoteJob.project_id == project_id)

    # Filtrar por cliente (através do projeto)
    if client_id:
        query = query.join(Project, BatchQuoteJob.project_id == Project.id).filter(
            Project.client_id == client_id
        )

    # Filtrar por tipo de entrada
    if input_type:
        query = query.filter(BatchQuoteJob.input_type == input_type)

    # Filtrar por status se especificado
    if status:
        try:
            status_enum = BatchJobStatus(status)
            query = query.filter(BatchQuoteJob.status == status_enum)
        except ValueError:
            pass  # Status invalido, ignorar filtro

    # Ordenar por data de criacao (mais recente primeiro)
    query = query.order_by(BatchQuoteJob.created_at.desc())

    # Otimização: Usar subquery para contagem total evitando carregamento duplo
    from sqlalchemy import func as sql_func
    count_query = db.query(sql_func.count(BatchQuoteJob.id))
    if batch_id:
        count_query = count_query.filter(BatchQuoteJob.id == batch_id)
    if project_id:
        count_query = count_query.filter(BatchQuoteJob.project_id == project_id)
    if client_id:
        count_query = count_query.join(Project, BatchQuoteJob.project_id == Project.id).filter(
            Project.client_id == client_id
        )
    if input_type:
        count_query = count_query.filter(BatchQuoteJob.input_type == input_type)
    if status:
        try:
            status_enum = BatchJobStatus(status)
            count_query = count_query.filter(BatchQuoteJob.status == status_enum)
        except ValueError:
            pass
    total = count_query.scalar()

    # Buscar apenas os campos necessários com paginação
    batches = query.offset((page - 1) * per_page).limit(per_page).all()

    items = [
        BatchListItem(
            id=b.id,
            status=b.status.value,
            input_type=b.input_type,
            created_at=b.created_at,
            total_items=b.total_items,
            completed_items=b.completed_items,
            failed_items=b.failed_items,
            progress_percentage=_calculate_progress(b),
            project_id=b.project_id,
            project_nome=b.project.nome if b.project else None,
        )
        for b in batches
    ]

    return BatchListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/{batch_id}/costs")
def get_batch_costs(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna resumo de custos e chamadas de API do lote."""
    from app.models.integration_log import IntegrationLog
    from sqlalchemy import func as sql_func

    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    # Buscar IDs das cotacoes do lote
    quote_ids = db.query(QuoteRequest.id).filter(
        QuoteRequest.batch_job_id == batch_id
    ).all()
    quote_ids = [q[0] for q in quote_ids]

    if not quote_ids:
        return {
            "batch_id": batch_id,
            "anthropic": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0},
            "serpapi": {"calls": 0, "google_shopping": 0, "immersive_product": 0},
            "total_cost_usd": 0,
            "total_cost_brl": 0
        }

    # Agregar logs do Anthropic
    anthropic_stats = db.query(
        sql_func.count(IntegrationLog.id).label('calls'),
        sql_func.coalesce(sql_func.sum(IntegrationLog.input_tokens), 0).label('input_tokens'),
        sql_func.coalesce(sql_func.sum(IntegrationLog.output_tokens), 0).label('output_tokens'),
        sql_func.coalesce(sql_func.sum(IntegrationLog.total_tokens), 0).label('total_tokens'),
        sql_func.coalesce(sql_func.sum(IntegrationLog.estimated_cost_usd), 0).label('cost_usd')
    ).filter(
        IntegrationLog.quote_request_id.in_(quote_ids),
        IntegrationLog.integration_type == 'anthropic'
    ).first()

    # Agregar logs do SerpAPI
    serpapi_total = db.query(
        sql_func.count(IntegrationLog.id)
    ).filter(
        IntegrationLog.quote_request_id.in_(quote_ids),
        IntegrationLog.integration_type == 'serpapi'
    ).scalar() or 0

    serpapi_shopping = db.query(
        sql_func.count(IntegrationLog.id)
    ).filter(
        IntegrationLog.quote_request_id.in_(quote_ids),
        IntegrationLog.integration_type == 'serpapi',
        IntegrationLog.api_used == 'google_shopping'
    ).scalar() or 0

    serpapi_immersive = db.query(
        sql_func.count(IntegrationLog.id)
    ).filter(
        IntegrationLog.quote_request_id.in_(quote_ids),
        IntegrationLog.integration_type == 'serpapi',
        IntegrationLog.api_used == 'immersive_product'
    ).scalar() or 0

    # Custo estimado SerpAPI (US$ 0.005 por chamada aproximadamente)
    serpapi_cost = serpapi_total * 0.005

    total_cost_usd = float(anthropic_stats.cost_usd or 0) + serpapi_cost
    total_cost_brl = total_cost_usd * 6.0  # Taxa aproximada

    return {
        "batch_id": batch_id,
        "anthropic": {
            "calls": anthropic_stats.calls or 0,
            "input_tokens": int(anthropic_stats.input_tokens or 0),
            "output_tokens": int(anthropic_stats.output_tokens or 0),
            "total_tokens": int(anthropic_stats.total_tokens or 0),
            "cost_usd": round(float(anthropic_stats.cost_usd or 0), 4)
        },
        "serpapi": {
            "calls": serpapi_total,
            "google_shopping": serpapi_shopping,
            "immersive_product": serpapi_immersive,
            "cost_usd": round(serpapi_cost, 4)
        },
        "total_cost_usd": round(total_cost_usd, 4),
        "total_cost_brl": round(total_cost_brl, 2)
    }
