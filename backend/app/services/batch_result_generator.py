"""
Gerador de arquivos de resultado para cotacoes em lote.
Gera ZIP com PDFs e Excel com resumo.
"""
import os
import zipfile
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
import pandas as pd

from app.models import QuoteRequest, QuoteSource
from app.models.quote_request import QuoteStatus
from app.models.batch_quote import BatchQuoteJob

logger = logging.getLogger(__name__)

# Diretorio para armazenar resultados de lote
BATCH_RESULTS_DIR = os.path.join("storage", "batch_results")


def ensure_results_dir():
    """Garante que o diretorio de resultados existe."""
    os.makedirs(BATCH_RESULTS_DIR, exist_ok=True)


def generate_batch_zip(db: Session, batch: BatchQuoteJob) -> Optional[str]:
    """
    Gera um arquivo ZIP contendo todos os PDFs das cotacoes do lote.

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
                    doc = quote.documents[0]  # Primeiro documento gerado
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

    # Gerar ZIP com PDFs
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
