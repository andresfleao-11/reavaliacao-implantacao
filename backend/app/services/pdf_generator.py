from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from typing import List, Dict, Optional
from datetime import datetime
import locale
from decimal import Decimal


class PDFGenerator:
    def __init__(self):
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
            except:
                pass

    def generate_quote_pdf(
        self,
        output_path: str,
        item_name: str,
        codigo: Optional[str],
        sources: List[Dict],
        valor_medio: Decimal,
        local: str,
        pesquisador: str,
        data_pesquisa: datetime,
        variacao_percentual: Optional[Decimal] = None,
        variacao_maxima_percent: Optional[float] = None,
        # Parâmetros para veículos FIPE
        is_vehicle: bool = False,
        fipe_data: Optional[Dict] = None,
    ):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=12*mm,
            bottomMargin=12*mm,
        )

        story = []
        styles = getSampleStyleSheet()

        # Estilos personalizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#000000'),
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
        )

        # Determinar se variação está OK ou não
        variacao_ok = True
        if variacao_percentual is not None and variacao_maxima_percent is not None:
            variacao_ok = float(variacao_percentual) <= variacao_maxima_percent

        # ========== CABEÇALHO PRINCIPAL (primeira página apenas) ==========
        title = Paragraph(f"Relatório de Cotação de Preços", title_style)
        story.append(title)
        story.append(Spacer(1, 4*mm))

        # Cabeçalho com informações resumidas
        if is_vehicle and fipe_data:
            # Layout específico para veículos FIPE
            header_data = [
                ['Código (Material):', codigo or 'N/A'],
                ['Item (Query de Busca):', item_name],
                ['Data da Pesquisa:', data_pesquisa.strftime('%d/%m/%Y')],
                ['Pesquisador:', pesquisador or 'N/A'],
                ['Local da Pesquisa:', local or 'N/A'],
                ['Código FIPE:', fipe_data.get('codigo_fipe', 'N/A')],
                ['Marca:', fipe_data.get('marca', 'N/A')],
                ['Modelo:', fipe_data.get('modelo', 'N/A')],
                ['Ano/Combustível:', fipe_data.get('ano_combustivel', 'N/A')],
                ['Valor FIPE:', f"R$ {valor_medio:.2f}".replace('.', ',')],
            ]
            # Não adicionar variação para veículos FIPE
        else:
            # Layout padrão para outros itens
            header_data = [
                ['Código (Material):', codigo or 'N/A'],
                ['Item (Query de Busca):', item_name],
                ['Data da Pesquisa:', data_pesquisa.strftime('%d/%m/%Y')],
                ['Pesquisador:', pesquisador or 'N/A'],
                ['Local da Pesquisa:', local or 'N/A'],
                ['Valor da Média:', f"R$ {valor_medio:.2f}".replace('.', ',')],
            ]

            # Adicionar variação se disponível (apenas para não-veículos)
            if variacao_percentual is not None:
                variacao_str = f"{float(variacao_percentual):.2f}%".replace('.', ',')
                header_data.append(['Variação Calculada:', variacao_str])

            if variacao_maxima_percent is not None:
                header_data.append(['Variação Máx. Configurada:', f"{variacao_maxima_percent:.1f}%".replace('.', ',')])

        header_table = Table(header_data, colWidths=[55*mm, 125*mm])

        # Estilo da tabela de cabeçalho
        header_table_style = [
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8E8E8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]

        # Colorir linha de variação calculada (apenas para não-veículos)
        if not is_vehicle and variacao_percentual is not None:
            variacao_row = len(header_data) - 2 if variacao_maxima_percent else len(header_data) - 1
            if variacao_ok:
                header_table_style.append(('BACKGROUND', (1, variacao_row), (1, variacao_row), colors.HexColor('#90EE90')))  # Verde
            else:
                header_table_style.append(('BACKGROUND', (1, variacao_row), (1, variacao_row), colors.HexColor('#FF6B6B')))  # Vermelho

        # Para veículos, destacar linha do Valor FIPE em verde
        if is_vehicle:
            valor_fipe_row = len(header_data) - 1  # Última linha é Valor FIPE
            header_table_style.append(('BACKGROUND', (1, valor_fipe_row), (1, valor_fipe_row), colors.HexColor('#90EE90')))

        header_table.setStyle(TableStyle(header_table_style))
        story.append(header_table)
        story.append(Spacer(1, 6*mm))

        # ========== COTAÇÕES INDIVIDUAIS ==========
        section_title = Paragraph("<b>Cotações Individuais:</b>", header_style)
        story.append(section_title)
        story.append(Spacer(1, 4*mm))

        for idx, source in enumerate(sources):
            # Tabela com dados da cotação individual
            cot_data = [
                ['Cotação', f"#{idx + 1} de {len(sources)}"],
                ['Item', item_name],
                ['Data da Pesquisa', data_pesquisa.strftime('%d/%m/%Y')],
                ['Valor R$', f"R$ {source['price_value']:.2f}".replace('.', ',')],
            ]

            cot_table = Table(cot_data, colWidths=[45*mm, 135*mm])
            cot_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            story.append(cot_table)
            story.append(Spacer(1, 2*mm))

            # Link da pesquisa
            link_style = ParagraphStyle(
                'Link',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.blue,
                wordWrap='CJK',
            )
            link_text = f'<b>Link:</b> <a href="{source["url"]}">{source["url"]}</a>'
            link_para = Paragraph(link_text, link_style)
            story.append(link_para)
            story.append(Spacer(1, 3*mm))

            # Imagem/Screenshot
            if source.get('screenshot_path'):
                try:
                    # Largura disponível = A4 (210mm) - margens (15mm + 15mm) = 180mm
                    # Altura disponível = A4 (297mm) - margens (12mm + 12mm) = 273mm
                    # Usar 80% da largura e 40% da altura vertical
                    content_width = 180*mm
                    content_height = 273*mm
                    img_width = content_width * 0.80  # 80% da largura do conteúdo
                    img_height = content_height * 0.40  # 40% da altura da página
                    img = Image(source['screenshot_path'], width=img_width, height=img_height, kind='proportional')
                    story.append(img)
                except Exception as e:
                    story.append(Paragraph(f"[Erro ao carregar imagem: {str(e)}]", styles['Normal']))
            else:
                story.append(Paragraph("[Screenshot não disponível]", styles['Normal']))

            story.append(Spacer(1, 6*mm))

            # Quebra de página entre cotações (exceto na última)
            if idx < len(sources) - 1:
                story.append(PageBreak())

        doc.build(story)

    def _format_date_extenso(self, date: datetime) -> str:
        try:
            weekday = date.strftime('%A')
            day = date.day
            month = date.strftime('%B')
            year = date.year
            return f"{weekday}, {day} de {month} de {year}"
        except:
            return date.strftime('%d/%m/%Y')
