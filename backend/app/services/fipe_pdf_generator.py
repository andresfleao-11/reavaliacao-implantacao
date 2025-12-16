"""
Gerador de PDF para cotações da Tabela FIPE

REQ-FIPE-002: Inclui screenshot de comprovação do site oficial FIPE
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from typing import Optional
import locale
import logging
import os

logger = logging.getLogger(__name__)


class FipePDFGenerator:
    """Gerador de PDF para cotações de veículos via Tabela FIPE"""

    def __init__(self):
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
            except:
                pass

    def generate(
        self,
        output_path: str,
        quote_request,
        fipe_result,
        analysis_result,
        screenshot_path: Optional[str] = None
    ):
        """
        Gera PDF com informações da cotação FIPE.

        Args:
            output_path: Caminho para salvar o PDF
            quote_request: Objeto QuoteRequest
            fipe_result: Resultado da busca FIPE (FipeSearchResult)
            analysis_result: Resultado da análise do Claude (ItemAnalysisResult)
            screenshot_path: Caminho para screenshot de comprovação (opcional)
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm,
        )

        story = []
        styles = getSampleStyleSheet()

        # Estilos personalizados
        title_style = ParagraphStyle(
            'FipeTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a5f7a'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        subtitle_style = ParagraphStyle(
            'FipeSubtitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#333333'),
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )

        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1a5f7a'),
            spaceBefore=12,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )

        price_style = ParagraphStyle(
            'FipePrice',
            parent=styles['Normal'],
            fontSize=24,
            textColor=colors.HexColor('#2e7d32'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=8,
            spaceAfter=8
        )

        # ========== CABEÇALHO ==========
        title = Paragraph("Cotação Tabela FIPE", title_style)
        story.append(title)

        # Subtítulo com data
        data_consulta = datetime.now().strftime('%d/%m/%Y às %H:%M')
        subtitle = Paragraph(f"Consulta realizada em {data_consulta}", subtitle_style)
        story.append(subtitle)
        story.append(Spacer(1, 8*mm))

        # ========== DADOS DO VEÍCULO (análise) ==========
        story.append(Paragraph("Dados do Veículo Pesquisado", section_title_style))

        veiculo_data = []

        if analysis_result.marca:
            veiculo_data.append(['Marca:', analysis_result.marca])
        if analysis_result.modelo:
            veiculo_data.append(['Modelo:', analysis_result.modelo])

        # Extrair dados das especificações se disponíveis
        especificacoes = {}
        if hasattr(analysis_result, 'especificacoes') and analysis_result.especificacoes:
            especificacoes = analysis_result.especificacoes
        elif hasattr(analysis_result, 'dict'):
            result_dict = analysis_result.dict()
            especificacoes = result_dict.get('especificacoes', {})

        essenciais = especificacoes.get('essenciais', {})
        complementares = especificacoes.get('complementares', {})

        if essenciais.get('ano_modelo'):
            veiculo_data.append(['Ano Modelo:', essenciais['ano_modelo']])
        if essenciais.get('ano_fabricacao'):
            veiculo_data.append(['Ano Fabricação:', essenciais['ano_fabricacao']])
        if essenciais.get('combustivel'):
            veiculo_data.append(['Combustível:', essenciais['combustivel'].title()])
        if essenciais.get('versao'):
            veiculo_data.append(['Versão:', essenciais['versao']])

        if complementares.get('cor'):
            veiculo_data.append(['Cor:', complementares['cor']])
        if complementares.get('placa'):
            veiculo_data.append(['Placa:', complementares['placa']])

        if analysis_result.natureza:
            tipo_veiculo = {
                'veiculo_carro': 'Automóvel',
                'veiculo_moto': 'Motocicleta',
                'veiculo_caminhao': 'Caminhão/Ônibus'
            }.get(analysis_result.natureza, analysis_result.natureza)
            veiculo_data.append(['Tipo:', tipo_veiculo])

        if veiculo_data:
            veiculo_table = Table(veiculo_data, colWidths=[50*mm, 130*mm])
            veiculo_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E3F2FD')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#90CAF9')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(veiculo_table)

        story.append(Spacer(1, 10*mm))

        # ========== RESULTADO FIPE ==========
        if fipe_result.success and fipe_result.price:
            story.append(Paragraph("Resultado da Consulta FIPE", section_title_style))

            # Preço em destaque
            price_paragraph = Paragraph(fipe_result.price.price, price_style)
            story.append(price_paragraph)
            story.append(Spacer(1, 4*mm))

            # Dados da FIPE
            fipe_data = [
                ['Código FIPE:', fipe_result.price.codeFipe],
                ['Marca:', fipe_result.price.brand],
                ['Modelo:', fipe_result.price.model],
                ['Ano Modelo:', str(fipe_result.price.modelYear)],
                ['Combustível:', f"{fipe_result.price.fuel} ({fipe_result.price.fuelAcronym})"],
                ['Mês de Referência:', fipe_result.price.referenceMonth],
            ]

            # Tipo de veículo
            tipo_veiculo_fipe = {
                1: 'Carro',
                2: 'Moto',
                3: 'Caminhão'
            }.get(fipe_result.price.vehicleType, str(fipe_result.price.vehicleType))
            fipe_data.append(['Tipo de Veículo:', tipo_veiculo_fipe])

            fipe_table = Table(fipe_data, colWidths=[50*mm, 130*mm])
            fipe_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F5E9')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#A5D6A7')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(fipe_table)

            story.append(Spacer(1, 10*mm))

            # ========== CAMINHO DA BUSCA ==========
            if fipe_result.search_path:
                story.append(Paragraph("Detalhes da Consulta", section_title_style))

                search_info = [
                    ['Chamadas à API:', str(fipe_result.api_calls)],
                ]

                if fipe_result.brand_name:
                    search_info.append(['Marca Encontrada:', fipe_result.brand_name])
                if fipe_result.model_name:
                    search_info.append(['Modelo Encontrado:', fipe_result.model_name])
                if fipe_result.year_id:
                    search_info.append(['Código Ano:', fipe_result.year_id])

                search_table = Table(search_info, colWidths=[50*mm, 130*mm])
                search_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFF3E0')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                    ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FFCC80')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(search_table)

        else:
            # Falha na consulta
            error_style = ParagraphStyle(
                'ErrorStyle',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#c62828'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceBefore=10,
                spaceAfter=10
            )
            error_msg = fipe_result.error_message or "Erro desconhecido na consulta FIPE"
            story.append(Paragraph(f"Consulta FIPE não retornou resultado: {error_msg}", error_style))

        story.append(Spacer(1, 10*mm))

        # ========== SCREENSHOT DE COMPROVAÇÃO ==========
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                story.append(Paragraph("Comprovação - Site Oficial FIPE", section_title_style))
                story.append(Spacer(1, 4*mm))

                # Calcular dimensões da imagem mantendo proporção
                # A4 width util = 210 - 15 - 15 = 180mm
                max_width = 180 * mm
                max_height = 120 * mm  # Limitar altura para caber na página

                # Criar imagem com tamanho automático
                img = Image(screenshot_path)

                # Calcular escala mantendo proporção
                img_width = img.drawWidth
                img_height = img.drawHeight

                if img_width > 0 and img_height > 0:
                    scale_w = max_width / img_width
                    scale_h = max_height / img_height
                    scale = min(scale_w, scale_h)

                    img.drawWidth = img_width * scale
                    img.drawHeight = img_height * scale

                story.append(img)

                # Nota sobre o screenshot
                screenshot_note = ParagraphStyle(
                    'ScreenshotNote',
                    parent=styles['Normal'],
                    fontSize=8,
                    textColor=colors.HexColor('#666666'),
                    alignment=TA_CENTER,
                    spaceBefore=4
                )
                story.append(Paragraph(
                    "Screenshot capturado automaticamente do site veiculos.fipe.org.br",
                    screenshot_note
                ))

                logger.info(f"Screenshot incluído no PDF: {screenshot_path}")

            except Exception as e:
                logger.warning(f"Erro ao incluir screenshot no PDF: {e}")
                # Nota de indisponibilidade
                note_style = ParagraphStyle(
                    'NoteStyle',
                    parent=styles['Normal'],
                    fontSize=9,
                    textColor=colors.HexColor('#ff9800'),
                    alignment=TA_CENTER,
                    spaceBefore=6
                )
                story.append(Paragraph(
                    "Screenshot indisponível - consultar site oficial: veiculos.fipe.org.br",
                    note_style
                ))

        story.append(Spacer(1, 10*mm))

        # ========== RODAPÉ ==========
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER
        )

        footer_text = """
        <para alignment="center">
        Fonte: API FIPE - Tabela de Preços de Veículos<br/>
        <a href="https://veiculos.fipe.org.br/" color="blue">https://veiculos.fipe.org.br/</a><br/><br/>
        Este documento foi gerado automaticamente pelo Sistema de Reavaliação Patrimonial.
        </para>
        """
        story.append(Paragraph(footer_text, footer_style))

        # Construir PDF
        try:
            doc.build(story)
            logger.info(f"FIPE PDF generated successfully: {output_path}")
        except Exception as e:
            logger.error(f"Error building FIPE PDF: {e}")
            raise
