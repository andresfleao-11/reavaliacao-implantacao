"""
Gerador de arquivos de resultado para cotacoes em lote.
Gera ZIP com PDFs e Excel com resumo.
"""
import os
import zipfile
import hashlib
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
import pandas as pd

from app.models import QuoteRequest, QuoteSource, File, GeneratedDocument, Setting
from app.models.quote_request import QuoteStatus
from app.models.batch_quote import BatchQuoteJob
from app.models.file import FileType
from app.models.vehicle_price import VehiclePriceBank
from app.models.project_config import ProjectConfigVersion
from app.services.pdf_generator import PDFGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

# Diretorio para armazenar resultados de lote
BATCH_RESULTS_DIR = os.path.join("storage", "batch_results")


def ensure_results_dir():
    """Garante que o diretorio de resultados existe."""
    os.makedirs(BATCH_RESULTS_DIR, exist_ok=True)


def _calculate_sha256(file_path: str) -> str:
    """Calcula o hash SHA256 de um arquivo."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_pdf_for_quote(db: Session, quote: QuoteRequest) -> Optional[str]:
    """
    Gera o PDF para uma cotacao individual.

    Returns:
        Caminho do PDF gerado ou None se erro.
    """
    # Verificar se ja existe PDF
    if quote.documents:
        doc = quote.documents[0]
        if doc.pdf_file and doc.pdf_file.storage_path and os.path.exists(doc.pdf_file.storage_path):
            logger.debug(f"PDF ja existe para cotacao {quote.id}")
            return doc.pdf_file.storage_path

    # Verificar se cotacao esta concluida
    if quote.status not in [QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW]:
        logger.debug(f"Cotacao {quote.id} nao esta concluida (status: {quote.status})")
        return None

    # Buscar fontes aceitas
    sources = db.query(QuoteSource).filter(
        QuoteSource.quote_request_id == quote.id,
        QuoteSource.is_accepted == True
    ).all()

    if not sources:
        logger.debug(f"Nenhuma fonte aceita para cotacao {quote.id}")
        return None

    # Preparar dados das fontes
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

    # Instanciar gerador de PDF
    pdf_generator = PDFGenerator()

    # Determinar nome do item
    item_name = "Item"
    input_type_str = quote.input_type.value if quote.input_type else "TEXT"

    if input_type_str in ("IMAGE", "IMAGE_BATCH", "GOOGLE_LENS"):
        if quote.claude_payload_json and "nome_canonico" in quote.claude_payload_json:
            item_name = quote.claude_payload_json["nome_canonico"]
    else:
        if quote.input_text:
            item_name = quote.input_text
        elif quote.claude_payload_json and "nome_canonico" in quote.claude_payload_json:
            item_name = quote.claude_payload_json["nome_canonico"]

    # Gerar nome do arquivo
    pdf_filename = pdf_generator.generate_filename(
        quote_id=quote.id,
        codigo=quote.codigo_item,
        item_name=item_name
    )
    pdf_path = os.path.join(settings.STORAGE_PATH, "pdfs", pdf_filename)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    # Detectar se e veiculo (FIPE)
    is_vehicle = False
    fipe_data = None

    if quote.claude_payload_json:
        natureza = quote.claude_payload_json.get("natureza", "")
        if natureza and natureza.startswith("veiculo_"):
            is_vehicle = True

    # Se for veiculo, buscar dados FIPE
    if is_vehicle:
        vehicle_price = db.query(VehiclePriceBank).filter(
            VehiclePriceBank.quote_request_id == quote.id
        ).first()

        if vehicle_price:
            fipe_data = {
                "codigo_fipe": vehicle_price.codigo_fipe,
                "marca": vehicle_price.brand_name,
                "modelo": vehicle_price.model_name,
                "ano_combustivel": f"{vehicle_price.year_model} {vehicle_price.fuel_type or ''}".strip()
            }

        # Para veiculos FIPE, usar APENAS a fonte FIPE
        sources_data = []

        # Buscar screenshot FIPE se existir
        fipe_screenshot_dir = os.path.join(settings.STORAGE_PATH, "screenshots", "fipe")
        fipe_screenshot_path = None
        if os.path.exists(fipe_screenshot_dir):
            for filename in os.listdir(fipe_screenshot_dir):
                if f"fipe_screenshot_{quote.id}_" in filename:
                    fipe_screenshot_path = os.path.join(fipe_screenshot_dir, filename)
                    break

        sources_data.append({
            "url": "https://veiculos.fipe.org.br/",
            "price_value": quote.valor_medio,
            "screenshot_path": fipe_screenshot_path
        })

    # Obter configuracao de variacao
    variacao_maxima = 25.0

    if quote.config_version_id:
        config_version = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.id == quote.config_version_id
        ).first()
        if config_version and config_version.variacao_maxima_percent is not None:
            variacao_maxima = float(config_version.variacao_maxima_percent)

    if variacao_maxima == 25.0:
        setting = db.query(Setting).filter(Setting.key == "parameters").first()
        if setting and setting.value_json:
            variacao_maxima = setting.value_json.get("variacao_maxima_percent", 25.0)

    try:
        # Gerar PDF
        pdf_generator.generate_quote_pdf(
            output_path=pdf_path,
            item_name=item_name,
            codigo=quote.codigo_item,
            sources=sources_data,
            valor_medio=quote.valor_medio,
            local=quote.local or "N/A",
            pesquisador=quote.pesquisador or "Sistema",
            data_pesquisa=datetime.now(),
            variacao_percentual=quote.variacao_percentual,
            variacao_maxima_percent=variacao_maxima,
            is_vehicle=is_vehicle,
            fipe_data=fipe_data,
            input_type=input_type_str,
            quote_id=quote.id
        )

        # Salvar registro do arquivo
        pdf_file = File(
            type=FileType.PDF,
            mime_type="application/pdf",
            storage_path=pdf_path,
            sha256=_calculate_sha256(pdf_path)
        )
        db.add(pdf_file)
        db.flush()

        # Criar registro do documento gerado
        generated_doc = GeneratedDocument(
            quote_request_id=quote.id,
            pdf_file_id=pdf_file.id
        )
        db.add(generated_doc)
        db.commit()

        logger.info(f"PDF gerado para cotacao {quote.id}: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"Erro ao gerar PDF para cotacao {quote.id}: {e}")
        db.rollback()
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return None


def generate_batch_zip(db: Session, batch: BatchQuoteJob) -> Optional[str]:
    """
    Gera um arquivo ZIP contendo todos os PDFs das cotacoes do lote.
    Gera os PDFs que ainda nao existem antes de criar o ZIP.

    Returns:
        Caminho do arquivo ZIP ou None se nenhum PDF disponivel.
    """
    ensure_results_dir()

    # Buscar cotacoes concluidas do lote
    quotes = db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch.id,
        QuoteRequest.status.in_([QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW])
    ).order_by(QuoteRequest.batch_index).all()

    if not quotes:
        logger.info(f"Nenhuma cotacao concluida para o lote {batch.id}")
        return None

    # Gerar PDFs que ainda nao existem
    logger.info(f"Verificando/gerando PDFs para {len(quotes)} cotacoes do lote {batch.id}")
    for quote in quotes:
        # Verificar se ja existe PDF
        has_pdf = False
        if quote.documents:
            doc = quote.documents[0]
            if doc.pdf_file and doc.pdf_file.storage_path and os.path.exists(doc.pdf_file.storage_path):
                has_pdf = True

        if not has_pdf:
            logger.info(f"Gerando PDF para cotacao {quote.id} (lote {batch.id})")
            generate_pdf_for_quote(db, quote)
            # Refresh para pegar o documento recem criado
            db.refresh(quote)

    # Nome do arquivo ZIP
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"lote_{batch.id}_pdfs_{timestamp}.zip"
    zip_path = os.path.join(BATCH_RESULTS_DIR, zip_filename)

    pdfs_added = 0
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for quote in quotes:
                # Obter PDF via relacionamento documents -> pdf_file -> storage_path
                pdf_path = None
                if quote.documents:
                    doc = quote.documents[0]
                    if doc.pdf_file and doc.pdf_file.storage_path:
                        pdf_path = doc.pdf_file.storage_path

                if pdf_path and os.path.exists(pdf_path):
                    # Nome do arquivo dentro do ZIP
                    nome_item = "item"
                    if quote.claude_payload_json and isinstance(quote.claude_payload_json, dict):
                        nome_item = quote.claude_payload_json.get("nome_canonico", "item")

                    # Sanitizar nome do arquivo
                    safe_name = "".join(c for c in nome_item if c.isalnum() or c in (' ', '-', '_')).strip()[:50]

                    if quote.codigo_item:
                        arcname = f"{quote.batch_index + 1:03d}_{quote.codigo_item}_{safe_name}.pdf"
                    else:
                        arcname = f"{quote.batch_index + 1:03d}_{safe_name}.pdf"

                    zipf.write(pdf_path, arcname)
                    pdfs_added += 1
                    logger.debug(f"Adicionado ao ZIP: {arcname}")

        if pdfs_added == 0:
            logger.info(f"Nenhum PDF disponivel para o lote {batch.id}")
            os.remove(zip_path)
            return None

        logger.info(f"ZIP gerado para lote {batch.id}: {zip_path} ({pdfs_added} PDFs)")
        return zip_path

    except Exception as e:
        logger.error(f"Erro ao gerar ZIP para lote {batch.id}: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return None


def generate_batch_excel(db: Session, batch: BatchQuoteJob, numero_cotacoes: int = 3) -> Optional[str]:
    """
    Gera um arquivo Excel com resumo das cotacoes do lote.

    Colunas:
    - Codigo (Material)
    - Descricao (input_text original)
    - Cotacao 1, 2, 3... (valores de cada fonte)
    - Valor Medio
    - Variacao Encontrada (%)
    - Numero da Cotacao
    - Data da Cotacao

    Args:
        db: Sessao do banco de dados
        batch: Job de lote
        numero_cotacoes: Numero de colunas de cotacao (padrao 3)

    Returns:
        Caminho do arquivo Excel ou None se erro.
    """
    ensure_results_dir()

    # Buscar cotacoes do lote
    quotes = db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch.id
    ).order_by(QuoteRequest.batch_index).all()

    if not quotes:
        logger.info(f"Nenhuma cotacao encontrada para o lote {batch.id}")
        return None

    # Preparar dados para o DataFrame
    data = []

    for quote in quotes:
        # Buscar fontes aceitas da cotacao
        sources = db.query(QuoteSource).filter(
            QuoteSource.quote_request_id == quote.id,
            QuoteSource.is_accepted == True
        ).order_by(QuoteSource.id).all()

        # Dados basicos
        row = {
            'Código (Material)': quote.codigo_item or '',
            'Descrição': quote.input_text or '',
        }

        # Adicionar colunas de cotacao
        for i in range(numero_cotacoes):
            col_name = f'Cotação {i + 1}'
            if i < len(sources):
                row[col_name] = sources[i].price_value
            else:
                row[col_name] = None

        # Valor medio, variacao, numero e data
        row['Valor Médio'] = quote.valor_medio
        row['Variação (%)'] = quote.variacao_percentual
        row['Nº Cotação'] = quote.id
        row['Data'] = quote.created_at.strftime('%d/%m/%Y %H:%M') if quote.created_at else ''
        row['Status'] = quote.status.value if quote.status else ''

        data.append(row)

    # Criar DataFrame
    df = pd.DataFrame(data)

    # Nome do arquivo Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"lote_{batch.id}_resumo_{timestamp}.xlsx"
    excel_path = os.path.join(BATCH_RESULTS_DIR, excel_filename)

    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Resumo')

            # Ajustar largura das colunas
            worksheet = writer.sheets['Resumo']
            worksheet.column_dimensions['A'].width = 20  # Codigo
            worksheet.column_dimensions['B'].width = 60  # Descricao

            # Colunas de cotacao
            col_letter = 'C'
            for i in range(numero_cotacoes):
                worksheet.column_dimensions[chr(ord(col_letter) + i)].width = 15

            # Demais colunas
            remaining_start = chr(ord('C') + numero_cotacoes)
            worksheet.column_dimensions[remaining_start].width = 15  # Valor Medio
            worksheet.column_dimensions[chr(ord(remaining_start) + 1)].width = 12  # Variacao
            worksheet.column_dimensions[chr(ord(remaining_start) + 2)].width = 12  # Numero
            worksheet.column_dimensions[chr(ord(remaining_start) + 3)].width = 18  # Data
            worksheet.column_dimensions[chr(ord(remaining_start) + 4)].width = 15  # Status

        logger.info(f"Excel gerado para lote {batch.id}: {excel_path} ({len(quotes)} linhas)")
        return excel_path

    except Exception as e:
        logger.error(f"Erro ao gerar Excel para lote {batch.id}: {e}")
        if os.path.exists(excel_path):
            os.remove(excel_path)
        return None


def generate_batch_results(db: Session, batch_id: int, numero_cotacoes: int = 3) -> dict:
    """
    Gera todos os arquivos de resultado do lote (ZIP e Excel).
    Atualiza os caminhos no modelo BatchQuoteJob.

    Args:
        db: Sessao do banco de dados
        batch_id: ID do lote
        numero_cotacoes: Numero de colunas de cotacao no Excel

    Returns:
        Dict com caminhos dos arquivos gerados.
    """
    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()
    if not batch:
        logger.error(f"Lote {batch_id} nao encontrado")
        return {"error": "Lote nao encontrado"}

    result = {
        "batch_id": batch_id,
        "zip_path": None,
        "excel_path": None
    }

    # Gerar ZIP com PDFs (inclui geracao de PDFs faltantes)
    zip_path = generate_batch_zip(db, batch)
    if zip_path:
        batch.result_zip_path = zip_path
        result["zip_path"] = zip_path

    # Gerar Excel com resumo
    excel_path = generate_batch_excel(db, batch, numero_cotacoes)
    if excel_path:
        batch.result_excel_path = excel_path
        result["excel_path"] = excel_path

    db.commit()

    logger.info(f"Resultados gerados para lote {batch_id}: ZIP={zip_path}, Excel={excel_path}")
    return result
