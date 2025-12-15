from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Form, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import QuoteRequest, QuoteSource, File, GeneratedDocument, IntegrationLog, Setting, User
from app.models.quote_request import QuoteStatus, QuoteInputType
from app.models.file import FileType
from app.models.project import Project
from app.models.project_config import ProjectConfigVersion
from app.utils.file_validation import validate_multiple_uploads, sanitize_filename, ALLOWED_IMAGE_EXTENSIONS
from app.api.schemas import (
    QuoteCreateResponse,
    QuoteDetailResponse,
    QuoteListResponse,
    QuoteListItem,
    QuoteSourceResponse,
    ProjectInfoResponse,
    IntegrationLogResponse,
    QuoteAttemptInfo
)
from app.tasks.quote_tasks import process_quote_request
from app.services.pdf_generator import PDFGenerator
from app.core.config import settings
from datetime import datetime
from decimal import Decimal
import os
import hashlib

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

# Configurar limiter para quotes
limiter = Limiter(key_func=get_remote_address)


@router.post("", response_model=QuoteCreateResponse)
@limiter.limit("10/minute")  # Máximo 10 cotações por minuto por IP
async def create_quote(
    request: Request,
    inputText: Optional[str] = Form(None),
    codigo: Optional[str] = Form(None),
    local: Optional[str] = Form(None),
    pesquisador: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    images: List[UploadFile] = FastAPIFile(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not inputText and not images:
        raise HTTPException(status_code=400, detail="Either inputText or images must be provided")

    # Validar imagens se foram enviadas
    validated_images = []
    if images and any(img.filename for img in images):
        # Filtrar apenas imagens com filename
        valid_images = [img for img in images if img.filename]

        # Validar arquivos (tamanho, tipo, magic bytes)
        image_contents = await validate_multiple_uploads(
            valid_images,
            max_files=5,
            allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
            max_size_per_file=5 * 1024 * 1024,  # 5MB por imagem
            max_total_size=20 * 1024 * 1024     # 20MB total
        )

        validated_images = list(zip(valid_images, image_contents))

    # Buscar versão ativa da configuração do projeto (se houver projeto)
    config_version_id = None
    if project_id:
        active_config = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.project_id == project_id,
            ProjectConfigVersion.ativo == True
        ).first()
        if active_config:
            config_version_id = active_config.id

    # Determinar o tipo de entrada
    has_images = images and any(img.filename for img in images)
    input_type = QuoteInputType.IMAGE if has_images else QuoteInputType.TEXT

    quote_request = QuoteRequest(
        status=QuoteStatus.PROCESSING,
        input_type=input_type,
        input_text=inputText,
        codigo_item=codigo,
        local=local,
        pesquisador=pesquisador,
        project_id=project_id,
        config_version_id=config_version_id
    )
    db.add(quote_request)
    db.commit()
    db.refresh(quote_request)

    # Salvar imagens validadas
    if validated_images:
        upload_dir = os.path.join(settings.STORAGE_PATH, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        for img, content in validated_images:
            # Sanitizar nome do arquivo
            safe_filename = sanitize_filename(img.filename)
            filename = f"input_{quote_request.id}_{safe_filename}"
            file_path = os.path.join(upload_dir, filename)

            # Salvar arquivo
            with open(file_path, "wb") as f:
                f.write(content)

            # Calcular hash SHA256
            sha256_hash = hashlib.sha256(content).hexdigest()

            # Registrar no banco
            file_record = File(
                type=FileType.INPUT_IMAGE,
                mime_type=img.content_type,
                storage_path=file_path,
                sha256=sha256_hash,
                quote_request_id=quote_request.id
            )
            db.add(file_record)

        db.commit()

    process_quote_request.delay(quote_request.id)

    return QuoteCreateResponse(quoteRequestId=quote_request.id)


@router.get("/{quote_id}", response_model=QuoteDetailResponse)
def get_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Otimizar com joinedload para evitar queries N+1
    quote_request = db.query(QuoteRequest)\
        .options(
            joinedload(QuoteRequest.sources),
            joinedload(QuoteRequest.documents),
            joinedload(QuoteRequest.project).joinedload(Project.client),
            joinedload(QuoteRequest.config_version),
            joinedload(QuoteRequest.integration_logs)
        )\
        .filter(QuoteRequest.id == quote_id)\
        .first()

    if not quote_request:
        raise HTTPException(status_code=404, detail="Quote request not found")

    sources_response = []
    for source in quote_request.sources:
        screenshot_url = None
        if source.screenshot_file_id:
            screenshot_url = f"/api/quotes/{quote_id}/screenshots/{source.screenshot_file_id}"

        sources_response.append(QuoteSourceResponse(
            id=source.id,
            url=source.url,
            domain=source.domain,
            page_title=source.page_title,
            price_value=source.price_value,
            currency=source.currency,
            extraction_method=source.extraction_method.value if source.extraction_method else None,
            captured_at=source.captured_at,
            is_outlier=source.is_outlier,
            is_accepted=source.is_accepted,
            screenshot_url=screenshot_url
        ))

    pdf_url = None
    if quote_request.documents:
        pdf_url = f"/api/quotes/{quote_id}/pdf"

    # Informações do projeto
    project_info = None
    if quote_request.project_id:
        project = db.query(Project).filter(Project.id == quote_request.project_id).first()
        if project:
            # Buscar versão ativa da configuração
            active_config = db.query(ProjectConfigVersion).filter(
                ProjectConfigVersion.project_id == project.id,
                ProjectConfigVersion.ativo == True
            ).first()

            project_info = ProjectInfoResponse(
                id=project.id,
                nome=project.nome,
                cliente_nome=project.client.nome if project.client else None,
                config_versao=active_config.versao if active_config else None
            )

    # Buscar parâmetros - prioridade: config do projeto > global > default
    numero_cotacoes = 3
    variacao_maxima = 25.0

    # Primeiro, verificar se há configuração do projeto associada
    if quote_request.config_version_id:
        config_version = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.id == quote_request.config_version_id
        ).first()
        if config_version:
            if config_version.numero_cotacoes_por_pesquisa is not None:
                numero_cotacoes = config_version.numero_cotacoes_por_pesquisa
            if config_version.variacao_maxima_percent is not None:
                variacao_maxima = float(config_version.variacao_maxima_percent)

    # Se não veio da config do projeto, usar parâmetros globais
    if numero_cotacoes == 3 and variacao_maxima == 25.0:
        setting = db.query(Setting).filter(Setting.key == "parameters").first()
        if setting and setting.value_json:
            numero_cotacoes = setting.value_json.get("numero_cotacoes_por_pesquisa", 3)
            variacao_maxima = setting.value_json.get("variacao_maxima_percent", 25.0)

    # Buscar histórico de tentativas
    attempt_history = []
    root_quote_id = quote_request.original_quote_id or quote_request.id

    # Buscar todas as cotações relacionadas (original + recotações)
    related_quotes = db.query(QuoteRequest).filter(
        (QuoteRequest.id == root_quote_id) |
        (QuoteRequest.original_quote_id == root_quote_id)
    ).order_by(QuoteRequest.attempt_number).all()

    for rq in related_quotes:
        attempt_history.append(QuoteAttemptInfo(
            id=rq.id,
            attempt_number=rq.attempt_number or 1,
            status=rq.status.value,
            created_at=rq.created_at,
            error_message=rq.error_message
        ))

    # Buscar cotação filha (se esta cotação já foi recotada)
    child_quote = db.query(QuoteRequest).filter(
        QuoteRequest.original_quote_id == quote_request.id
    ).first()

    # Se não encontrou diretamente, verificar se é uma cotação raiz
    if not child_quote and quote_request.original_quote_id is None:
        # Esta é uma cotação raiz, verificar se tem filhas diretas
        child_quote = db.query(QuoteRequest).filter(
            QuoteRequest.original_quote_id == quote_request.id
        ).first()

    child_quote_id = child_quote.id if child_quote else None

    return QuoteDetailResponse(
        id=quote_request.id,
        status=quote_request.status.value,
        input_type=quote_request.input_type.value if quote_request.input_type else None,
        created_at=quote_request.created_at,
        input_text=quote_request.input_text,
        codigo_item=quote_request.codigo_item,
        claude_payload_json=quote_request.claude_payload_json,
        search_query_final=quote_request.search_query_final,
        local=quote_request.local,
        pesquisador=quote_request.pesquisador,
        valor_medio=quote_request.valor_medio,
        valor_minimo=quote_request.valor_minimo,
        valor_maximo=quote_request.valor_maximo,
        variacao_percentual=quote_request.variacao_percentual,
        error_message=quote_request.error_message,
        sources=sources_response,
        pdf_url=pdf_url,
        project_id=quote_request.project_id,
        project=project_info,
        current_step=quote_request.current_step,
        progress_percentage=quote_request.progress_percentage,
        step_details=quote_request.step_details,
        numero_cotacoes_configurado=numero_cotacoes,
        variacao_maxima_percent=variacao_maxima,
        attempt_number=quote_request.attempt_number or 1,
        original_quote_id=quote_request.original_quote_id,
        attempt_history=attempt_history,
        child_quote_id=child_quote_id,
        batch_job_id=quote_request.batch_job_id
    )


@router.get("", response_model=QuoteListResponse)
def list_quotes(
    page: int = 1,
    per_page: int = 20,
    quote_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista cotações com filtros.

    Parâmetros:
    - quote_id: Filtrar por número/ID da cotação
    - search: Buscar na descrição (input_text)
    - status: Filtrar por status (PROCESSING, DONE, ERROR, CANCELLED, AWAITING_REVIEW)
    - project_id: Filtrar por projeto
    - date_from: Data inicial (formato: YYYY-MM-DD)
    - date_to: Data final (formato: YYYY-MM-DD)
    """
    from datetime import datetime

    offset = (page - 1) * per_page

    query = db.query(QuoteRequest).options(
        joinedload(QuoteRequest.project).joinedload(Project.client)
    )

    count_query = db.query(QuoteRequest)

    # Filtro por ID da cotação
    if quote_id is not None:
        query = query.filter(QuoteRequest.id == quote_id)
        count_query = count_query.filter(QuoteRequest.id == quote_id)

    # Filtro por busca na descrição
    if search:
        search_filter = QuoteRequest.input_text.ilike(f"%{search}%")
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)

    # Filtro por status
    if status:
        try:
            status_enum = QuoteStatus(status)
            query = query.filter(QuoteRequest.status == status_enum)
            count_query = count_query.filter(QuoteRequest.status == status_enum)
        except ValueError:
            pass  # Status inválido, ignorar

    # Filtro por projeto
    if project_id is not None:
        query = query.filter(QuoteRequest.project_id == project_id)
        count_query = count_query.filter(QuoteRequest.project_id == project_id)

    # Filtro por período
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(QuoteRequest.created_at >= date_from_parsed)
            count_query = count_query.filter(QuoteRequest.created_at >= date_from_parsed)
        except ValueError:
            pass  # Data inválida, ignorar

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d")
            # Adicionar 1 dia para incluir o dia inteiro
            from datetime import timedelta
            date_to_parsed = date_to_parsed + timedelta(days=1)
            query = query.filter(QuoteRequest.created_at < date_to_parsed)
            count_query = count_query.filter(QuoteRequest.created_at < date_to_parsed)
        except ValueError:
            pass  # Data inválida, ignorar

    total = count_query.count()

    quotes = query.order_by(
        QuoteRequest.created_at.desc()
    ).offset(offset).limit(per_page).all()

    items = []
    for quote in quotes:
        nome_item = None
        if quote.claude_payload_json and "nome_canonico" in quote.claude_payload_json:
            nome_item = quote.claude_payload_json["nome_canonico"]

        project_nome = None
        cliente_nome = None
        if quote.project:
            project_nome = quote.project.nome
            if quote.project.client:
                cliente_nome = quote.project.client.nome

        items.append(QuoteListItem(
            id=quote.id,
            status=quote.status.value,
            input_type=quote.input_type.value if quote.input_type else None,
            created_at=quote.created_at,
            codigo_item=quote.codigo_item,
            nome_item=nome_item,
            valor_medio=quote.valor_medio,
            project_id=quote.project_id,
            project_nome=project_nome,
            cliente_nome=cliente_nome
        ))

    return QuoteListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/{quote_id}/generate-pdf")
def generate_pdf(quote_id: int, db: Session = Depends(get_db)):
    """Generate PDF on demand for a completed quote request"""
    quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()

    if not quote_request:
        raise HTTPException(status_code=404, detail="Quote request not found")

    if quote_request.status != QuoteStatus.DONE:
        raise HTTPException(status_code=400, detail="Quote request is not completed yet")

    # Check if PDF already exists
    existing_doc = db.query(GeneratedDocument).filter(
        GeneratedDocument.quote_request_id == quote_id
    ).first()

    if existing_doc:
        pdf_file = db.query(File).filter(File.id == existing_doc.pdf_file_id).first()
        if pdf_file and os.path.exists(pdf_file.storage_path):
            return {"message": "PDF already exists", "pdf_url": f"/api/quotes/{quote_id}/pdf"}

    # Get sources for the quote
    sources = db.query(QuoteSource).filter(
        QuoteSource.quote_request_id == quote_id,
        QuoteSource.is_accepted == True
    ).all()

    if not sources:
        raise HTTPException(status_code=400, detail="No valid sources found for this quote")

    # Prepare sources data for PDF
    sources_data = []
    for source in sources:
        screenshot_path = None
        if source.screenshot_file_id:
            screenshot_file = db.query(File).filter(File.id == source.screenshot_file_id).first()
            if screenshot_file:
                screenshot_path = screenshot_file.storage_path

        sources_data.append({
            "url": source.url,
            "price_value": source.price_value,
            "screenshot_path": screenshot_path
        })

    # Generate PDF
    pdf_generator = PDFGenerator()
    pdf_filename = f"cotacao_{quote_id}.pdf"
    pdf_path = os.path.join(settings.STORAGE_PATH, "pdfs", pdf_filename)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    # Get item name from claude_payload_json
    item_name = "Item"
    if quote_request.claude_payload_json and "nome_canonico" in quote_request.claude_payload_json:
        item_name = quote_request.claude_payload_json["nome_canonico"]

    # Get variation settings - prioridade: config do projeto > global > default
    variacao_maxima = 25.0

    # Verificar se há configuração do projeto associada
    if quote_request.config_version_id:
        config_version = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.id == quote_request.config_version_id
        ).first()
        if config_version and config_version.variacao_maxima_percent is not None:
            variacao_maxima = float(config_version.variacao_maxima_percent)

    # Se não veio da config do projeto, usar parâmetros globais
    if variacao_maxima == 25.0:
        setting = db.query(Setting).filter(Setting.key == "parameters").first()
        if setting and setting.value_json:
            variacao_maxima = setting.value_json.get("variacao_maxima_percent", 25.0)

    pdf_generator.generate_quote_pdf(
        output_path=pdf_path,
        item_name=item_name,
        codigo=quote_request.codigo_item,
        sources=sources_data,
        valor_medio=quote_request.valor_medio,
        local=quote_request.local or "N/A",
        pesquisador=quote_request.pesquisador or "Sistema",
        data_pesquisa=datetime.now(),
        variacao_percentual=quote_request.variacao_percentual,
        variacao_maxima_percent=variacao_maxima
    )

    # Calculate SHA256
    sha256_hash = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    # Save file record
    pdf_file = File(
        type=FileType.PDF,
        mime_type="application/pdf",
        storage_path=pdf_path,
        sha256=sha256_hash.hexdigest()
    )
    db.add(pdf_file)
    db.flush()

    # Create generated document record
    generated_doc = GeneratedDocument(
        quote_request_id=quote_id,
        pdf_file_id=pdf_file.id
    )
    db.add(generated_doc)
    db.commit()

    return {"message": "PDF generated successfully", "pdf_url": f"/api/quotes/{quote_id}/pdf"}


@router.get("/{quote_id}/pdf")
def download_pdf(quote_id: int, db: Session = Depends(get_db)):
    quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()

    if not quote_request:
        raise HTTPException(status_code=404, detail="Quote request not found")

    document = db.query(GeneratedDocument).filter(
        GeneratedDocument.quote_request_id == quote_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="PDF not found. Please generate it first.")

    pdf_file = db.query(File).filter(File.id == document.pdf_file_id).first()

    if not pdf_file or not os.path.exists(pdf_file.storage_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(
        pdf_file.storage_path,
        media_type="application/pdf",
        filename=f"cotacao_{quote_id}.pdf"
    )


@router.get("/{quote_id}/screenshots/{file_id}")
def get_screenshot(quote_id: int, file_id: int, db: Session = Depends(get_db)):
    file_record = db.query(File).filter(
        File.id == file_id,
        File.type == FileType.SCREENSHOT
    ).first()

    if not file_record or not os.path.exists(file_record.storage_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(
        file_record.storage_path,
        media_type=file_record.mime_type or "image/png"
    )


@router.post("/{quote_id}/cancel")
def cancel_quote(quote_id: int, db: Session = Depends(get_db)):
    """Cancela uma cotação em andamento"""
    quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()

    if not quote_request:
        raise HTTPException(status_code=404, detail="Quote request not found")

    if quote_request.status != QuoteStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel quote with status {quote_request.status.value}"
        )

    quote_request.status = QuoteStatus.CANCELLED
    quote_request.error_message = "Cotação cancelada pelo usuário"
    db.commit()

    return {"message": "Quote cancelled successfully"}


@router.post("/{quote_id}/requote", response_model=QuoteCreateResponse)
def requote(quote_id: int, db: Session = Depends(get_db)):
    """Cria uma nova cotação baseada em uma cotação existente (cancelada ou com erro)"""
    original_quote = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()

    if not original_quote:
        raise HTTPException(status_code=404, detail="Quote request not found")

    if original_quote.status not in [QuoteStatus.CANCELLED, QuoteStatus.ERROR]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot requote a quote with status {original_quote.status.value}"
        )

    # Verificar se já existe uma recotação para esta cotação
    existing_child = db.query(QuoteRequest).filter(
        QuoteRequest.original_quote_id == quote_id
    ).first()

    if existing_child:
        raise HTTPException(
            status_code=400,
            detail=f"Esta cotação já foi recotada. Nova cotação: #{existing_child.id}"
        )

    # Determinar o original_quote_id e attempt_number
    # Se a cotação original já tem um original_quote_id, usar esse (é uma cadeia de recotações)
    # Caso contrário, o original é a própria cotação
    root_quote_id = original_quote.original_quote_id or original_quote.id

    # Contar quantas tentativas já existem para essa cotação raiz
    existing_attempts = db.query(QuoteRequest).filter(
        (QuoteRequest.id == root_quote_id) |
        (QuoteRequest.original_quote_id == root_quote_id)
    ).count()

    # Buscar versão ativa da configuração do projeto (pode ter mudado desde a cotação original)
    config_version_id = None
    if original_quote.project_id:
        active_config = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.project_id == original_quote.project_id,
            ProjectConfigVersion.ativo == True
        ).first()
        if active_config:
            config_version_id = active_config.id

    # Criar nova cotação com os mesmos dados (preservar input_type)
    new_quote = QuoteRequest(
        status=QuoteStatus.PROCESSING,
        input_type=original_quote.input_type,  # Preservar tipo de entrada
        input_text=original_quote.input_text,
        codigo_item=original_quote.codigo_item,
        local=original_quote.local,
        pesquisador=original_quote.pesquisador,
        project_id=original_quote.project_id,
        config_version_id=config_version_id,
        original_quote_id=root_quote_id,
        attempt_number=existing_attempts + 1
    )
    db.add(new_quote)
    db.commit()
    db.refresh(new_quote)

    # Copiar imagens de entrada se existirem
    if original_quote.input_images:
        for original_file in original_quote.input_images:
            if os.path.exists(original_file.storage_path):
                # Criar novo arquivo apontando para o mesmo storage_path
                new_file = File(
                    type=FileType.INPUT_IMAGE,
                    mime_type=original_file.mime_type,
                    storage_path=original_file.storage_path,
                    sha256=original_file.sha256,
                    quote_request_id=new_quote.id
                )
                db.add(new_file)
        db.commit()

    # Iniciar processamento
    process_quote_request.delay(new_quote.id)

    return QuoteCreateResponse(quoteRequestId=new_quote.id)


@router.get("/{quote_id}/integration-logs", response_model=List[IntegrationLogResponse])
def get_integration_logs(quote_id: int, db: Session = Depends(get_db)):
    """Retorna os logs de integrações (Anthropic e SerpAPI) para uma cotação"""
    quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()

    if not quote_request:
        raise HTTPException(status_code=404, detail="Quote request not found")

    # Buscar logs ordenados por data de criação
    logs = db.query(IntegrationLog).filter(
        IntegrationLog.quote_request_id == quote_id
    ).order_by(IntegrationLog.created_at).all()

    return logs


@router.delete("/admin/clear-all-data")
def clear_all_quote_data(db: Session = Depends(get_db)):
    """
    ADMIN: Limpa todas as cotações e dados relacionados.
    Mantém: usuários, configurações de integração, clientes, projetos, materiais.
    """
    import shutil

    try:
        # Importar modelos necessários
        from app.models.financial import FinancialTransaction
        from app.models.bank_price import BankPrice
        from app.models.project_config import ProjectBankPrice

        # 1. Deletar transações financeiras (dependem de cotações)
        db.query(FinancialTransaction).delete()

        # 2. Deletar logs de integração (dependem de cotações)
        db.query(IntegrationLog).delete()

        # 3. Deletar documentos gerados
        db.query(GeneratedDocument).delete()

        # 4. Deletar fontes de cotação (QuoteSource)
        db.query(QuoteSource).delete()

        # 5. Deletar arquivos (screenshots, pdfs, uploads)
        db.query(File).delete()

        # 6. Deletar cotações
        db.query(QuoteRequest).delete()

        # 7. Deletar preços do banco de preços global
        db.query(BankPrice).delete()

        # 8. Deletar preços do banco de preços dos projetos
        db.query(ProjectBankPrice).delete()

        db.commit()

        # 9. Limpar arquivos físicos do storage
        storage_dirs = ['uploads', 'pdfs', 'screenshots']
        for dir_name in storage_dirs:
            dir_path = os.path.join(settings.STORAGE_PATH, dir_name)
            if os.path.exists(dir_path):
                for file_name in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, file_name)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        pass  # Ignorar erros ao deletar arquivos

        return {
            "success": True,
            "message": "Todos os dados de cotações foram limpos com sucesso",
            "deleted": [
                "quote_requests",
                "quote_sources",
                "integration_logs",
                "financial_transactions",
                "generated_documents",
                "files",
                "bank_prices",
                "project_bank_prices"
            ]
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao limpar dados: {str(e)}")


# ============== GOOGLE LENS ENDPOINTS ==============

@router.post("/lens/search", response_model=dict)
async def lens_search(
    image: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db)
):
    """
    Busca produtos usando Google Lens.

    Etapa 1 do fluxo Google Lens:
    - Faz upload da imagem para imgbb (URL pública)
    - Envia URL para SerpAPI Google Lens
    - Retorna lista de produtos identificados
    """
    from app.services.google_lens_service import GoogleLensService, upload_image_to_imgbb
    from app.core.config import settings
    from app.models.integration_setting import IntegrationSetting
    from app.core.security import decrypt_value

    # Get SerpAPI key
    serpapi_key = None
    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == "SERPAPI"
    ).first()

    if integration and integration.settings_json.get("api_key"):
        try:
            serpapi_key = decrypt_value(integration.settings_json.get("api_key"))
        except:
            serpapi_key = integration.settings_json.get("api_key")

    if not serpapi_key:
        serpapi_key = settings.SERPAPI_API_KEY

    if not serpapi_key:
        raise HTTPException(status_code=400, detail="SerpAPI key not configured")

    # Get imgbb API key
    imgbb_key = None
    imgbb_integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == "IMGBB"
    ).first()

    if imgbb_integration and imgbb_integration.settings_json.get("api_key"):
        try:
            imgbb_key = decrypt_value(imgbb_integration.settings_json.get("api_key"))
        except:
            imgbb_key = imgbb_integration.settings_json.get("api_key")

    if not imgbb_key:
        imgbb_key = os.environ.get("IMGBB_API_KEY")

    if not imgbb_key:
        raise HTTPException(
            status_code=400,
            detail="imgbb API key not configured. Configure em Configurações > Integrações ou defina IMGBB_API_KEY no ambiente."
        )

    # Read image content
    content = await image.read()

    # Upload image to imgbb for public URL
    image_url = await upload_image_to_imgbb(content, imgbb_key)

    if not image_url:
        raise HTTPException(
            status_code=500,
            detail="Falha ao fazer upload da imagem. Verifique a chave da API imgbb."
        )

    # Search using Google Lens
    lens_service = GoogleLensService(api_key=serpapi_key)
    result = await lens_service.search_by_image_url(image_url)

    return {
        "success": True,
        "total_products": result.total_results,
        "products": [p.dict() for p in result.products[:20]],  # Limit to 20 products
        "image_url": image_url,
        "api_calls": lens_service.get_api_calls()
    }


@router.get("/lens/image/{filename}")
async def serve_lens_image(filename: str):
    """Serve temporary lens images for SerpAPI to access"""
    file_path = os.path.join(settings.STORAGE_PATH, "lens_temp", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")

    # Determine content type
    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"
    elif filename.lower().endswith(".gif"):
        content_type = "image/gif"
    elif filename.lower().endswith(".webp"):
        content_type = "image/webp"

    return FileResponse(file_path, media_type=content_type)


@router.post("/lens/extract-specs", response_model=dict)
async def lens_extract_specs(
    product_url: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Extrai especificações de um produto identificado pelo Google Lens.

    Etapa 2 do fluxo Google Lens:
    - Acessa o link do produto
    - Extrai nome, marca, modelo e especificações
    """
    from app.services.google_lens_service import GoogleLensService, ProductSpecs
    from app.services.claude_client import ClaudeClient
    from app.core.config import settings
    from app.models.integration_setting import IntegrationSetting
    from app.core.security import decrypt_value

    # Get API keys
    serpapi_key = None
    anthropic_key = None
    anthropic_model = None

    # SerpAPI key
    serpapi_integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == "SERPAPI"
    ).first()
    if serpapi_integration and serpapi_integration.settings_json.get("api_key"):
        try:
            serpapi_key = decrypt_value(serpapi_integration.settings_json.get("api_key"))
        except:
            serpapi_key = serpapi_integration.settings_json.get("api_key")
    if not serpapi_key:
        serpapi_key = settings.SERPAPI_API_KEY

    # Anthropic key
    anthropic_integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == "ANTHROPIC"
    ).first()
    if anthropic_integration:
        if anthropic_integration.settings_json.get("api_key"):
            try:
                anthropic_key = decrypt_value(anthropic_integration.settings_json.get("api_key"))
            except:
                anthropic_key = anthropic_integration.settings_json.get("api_key")
        anthropic_model = anthropic_integration.settings_json.get("model")

    if not anthropic_key:
        anthropic_key = settings.ANTHROPIC_API_KEY
    if not anthropic_model:
        anthropic_model = settings.ANTHROPIC_MODEL

    # Initialize services
    lens_service = GoogleLensService(api_key=serpapi_key)
    claude_client = ClaudeClient(api_key=anthropic_key, model=anthropic_model) if anthropic_key else None

    # Extract specs from product URL
    specs = await lens_service.extract_product_specs_from_url(product_url, claude_client)

    return {
        "success": True,
        "specs": specs.dict()
    }


@router.post("/lens/create-quote", response_model=QuoteCreateResponse)
async def create_quote_from_lens(
    product_url: str = Form(...),
    product_title: str = Form(...),
    marca: Optional[str] = Form(None),
    modelo: Optional[str] = Form(None),
    tipo_produto: Optional[str] = Form(None),
    especificacoes: Optional[str] = Form(None),  # JSON string
    codigo: Optional[str] = Form(None),
    local: Optional[str] = Form(None),
    pesquisador: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    image: Optional[UploadFile] = FastAPIFile(None),
    lens_api_calls: Optional[str] = Form(None),  # JSON string of API calls from Google Lens search
    db: Session = Depends(get_db)
):
    """
    Cria uma cotação a partir de um produto identificado pelo Google Lens.

    Etapa 3 do fluxo Google Lens:
    - Usa as specs extraídas para criar a cotação
    - Continua com o fluxo normal de busca de preços
    """
    import json
    from fastapi import HTTPException

    # Validar dados obrigatórios para criação de cotação
    if not product_title or not product_title.strip():
        raise HTTPException(
            status_code=400,
            detail="Título do produto é obrigatório para criar uma cotação"
        )

    if not product_url or not product_url.strip():
        raise HTTPException(
            status_code=400,
            detail="URL do produto é obrigatória para criar uma cotação"
        )

    # Parse especificacoes JSON
    specs_dict = {}
    if especificacoes:
        try:
            specs_dict = json.loads(especificacoes)
        except:
            pass

    # Parse lens_api_calls JSON
    api_calls = []
    if lens_api_calls:
        try:
            api_calls = json.loads(lens_api_calls)
        except:
            pass

    # Build input text from specs (for the regular flow)
    input_parts = [f"Produto: {product_title}"]
    if marca:
        input_parts.append(f"Marca: {marca}")
    if modelo:
        input_parts.append(f"Modelo: {modelo}")
    if tipo_produto:
        input_parts.append(f"Tipo: {tipo_produto}")

    # Add specs
    for key, value in specs_dict.items():
        if value:
            input_parts.append(f"{key}: {value}")

    input_parts.append(f"Fonte: {product_url}")

    input_text = "\n".join(input_parts)

    # Get active config version for project
    config_version_id = None
    if project_id:
        active_config = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.project_id == project_id,
            ProjectConfigVersion.ativo == True
        ).first()
        if active_config:
            config_version_id = active_config.id

    # Create quote request - tipo GOOGLE_LENS
    quote_request = QuoteRequest(
        status=QuoteStatus.PROCESSING,
        input_type=QuoteInputType.GOOGLE_LENS,
        input_text=input_text,
        codigo_item=codigo,
        local=local,
        pesquisador=pesquisador,
        project_id=project_id,
        config_version_id=config_version_id
    )
    db.add(quote_request)
    db.commit()
    db.refresh(quote_request)

    # Save image if provided
    if image and image.filename:
        upload_dir = os.path.join(settings.STORAGE_PATH, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"input_{quote_request.id}_{image.filename}"
        file_path = os.path.join(upload_dir, filename)

        content = await image.read()
        with open(file_path, "wb") as f:
            f.write(content)

        sha256_hash = hashlib.sha256(content).hexdigest()

        file_record = File(
            type=FileType.INPUT_IMAGE,
            mime_type=image.content_type,
            storage_path=file_path,
            sha256=sha256_hash,
            quote_request_id=quote_request.id
        )
        db.add(file_record)
        db.commit()

    # Register Google Lens API calls in integration logs
    if api_calls:
        from app.models.financial import ApiCostConfig

        # Get cost per Google Lens call (using SerpAPI costs)
        serpapi_cost = db.query(ApiCostConfig).filter(
            ApiCostConfig.api_name == "serpapi",
            ApiCostConfig.is_active == True
        ).first()

        unit_cost = 0.01  # Default cost per call
        if serpapi_cost and serpapi_cost.cost_per_call_brl:
            unit_cost = float(serpapi_cost.cost_per_call_brl)

        for call in api_calls:
            log_entry = IntegrationLog(
                quote_request_id=quote_request.id,
                integration_type='serpapi',
                activity=call.get('activity', 'Google Lens search'),
                api_used=call.get('api_used', 'google_lens'),
                search_url=call.get('search_url'),
                product_link=product_url,
                request_data={
                    'engine': 'google_lens',
                    'type': 'products',
                    'product_title': product_title
                },
                response_summary={
                    'product_found': True,
                    'product_url': product_url
                }
            )
            db.add(log_entry)

        db.commit()

    # Start processing
    process_quote_request.delay(quote_request.id)

    return QuoteCreateResponse(quoteRequestId=quote_request.id)
