from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import List, Dict, Optional
from datetime import datetime
import locale
from decimal import Decimal
import os


class PDFGenerator:
    # Caminho para os assets
    FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
    LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "Union lk.png")

    # Larguras das colunas (primeira coluna menor para o logo)
    FIRST_COL_WIDTH = 55 * mm
    SECOND_COL_WIDTH = 125 * mm

    def __init__(self):
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
            except:
                pass

        # Registrar fontes Poppins
        self._register_fonts()

    def _register_fonts(self):
        """Registra as fontes Poppins no ReportLab"""
        try:
            poppins_regular = os.path.join(self.FONTS_DIR, "Poppins-Regular.ttf")
            poppins_bold = os.path.join(self.FONTS_DIR, "Poppins-Bold.ttf")

            if os.path.exists(poppins_regular):
                pdfmetrics.registerFont(TTFont('Poppins', poppins_regular))
            if os.path.exists(poppins_bold):
                pdfmetrics.registerFont(TTFont('Poppins-Bold', poppins_bold))
        except Exception as e:
            print(f"Warning: Could not register Poppins fonts: {e}")

    def _get_font_name(self, bold: bool = False) -> str:
        """Retorna o nome da fonte (Poppins se disponível, senão Helvetica)"""
        try:
            if bold:
                return 'Poppins-Bold' if pdfmetrics.getFont('Poppins-Bold') else 'Helvetica-Bold'
            return 'Poppins' if pdfmetrics.getFont('Poppins') else 'Helvetica'
        except:
            return 'Helvetica-Bold' if bold else 'Helvetica'

    def generate_filename(
        self,
        quote_id: int,
        codigo: Optional[str],
        item_name: str
    ) -> str:
        """
        Gera o nome do arquivo PDF no formato:
        #[numero_cotacao] - [Código (Material)] - [item_name]
        """
        # Sanitizar o nome do item para uso em nome de arquivo
        safe_item_name = "".join(c for c in item_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_item_name = safe_item_name[:50]  # Limitar tamanho

        if codigo:
            filename = f"#{quote_id} - {codigo} - {safe_item_name}.pdf"
        else:
            filename = f"#{quote_id} - {safe_item_name}.pdf"

        return filename

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
        # Novo parâmetro para identificar tipo de busca
        input_type: str = "TEXT",  # TEXT ou IMAGE
        quote_id: Optional[int] = None,
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

        font_regular = self._get_font_name(bold=False)
        font_bold = self._get_font_name(bold=True)

        # Estilos personalizados com Poppins
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#000000'),
            spaceAfter=0,
            alignment=TA_LEFT,
            fontName=font_bold
        )

        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontSize=11,
            fontName=font_bold,
            spaceAfter=4,
        )

        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=10,
            fontName=font_bold,
        )

        link_title_style = ParagraphStyle(
            'LinkTitle',
            parent=styles['Normal'],
            fontSize=9,
            fontName=font_bold,
        )

        link_style = ParagraphStyle(
            'Link',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.blue,
            wordWrap='CJK',
            fontName=font_regular,
        )

        # Estilo para número da cotação no canto direito
        quote_number_style = ParagraphStyle(
            'QuoteNumber',
            parent=styles['Normal'],
            fontSize=10,
            fontName=font_bold,
            alignment=TA_RIGHT,
        )

        # Determinar se variação está OK ou não
        variacao_ok = True
        if variacao_percentual is not None and variacao_maxima_percent is not None:
            variacao_ok = float(variacao_percentual) <= variacao_maxima_percent

        total_sources = len(sources)

        # ========== PÁGINA 1: RESUMO ==========
        story.extend(self._build_header(title_style, font_bold, font_regular))

        # Seção "Resumo de cotações"
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph("Resumo de cotações", section_title_style))
        story.append(Spacer(1, 3*mm))

        # Tabela de resumo
        if is_vehicle and fipe_data:
            # Layout específico para veículos FIPE
            header_data = [
                ['Código (Material):', codigo or 'N/A'],
                ['Item:', item_name],
                ['Data da Pesquisa:', data_pesquisa.strftime('%d/%m/%Y')],
                ['Pesquisador:', pesquisador or 'N/A'],
                ['Local da Pesquisa:', local or 'N/A'],
                ['Código FIPE:', fipe_data.get('codigo_fipe', 'N/A')],
                ['Marca:', fipe_data.get('marca', 'N/A')],
                ['Modelo:', fipe_data.get('modelo', 'N/A')],
                ['Ano/Combustível:', fipe_data.get('ano_combustivel', 'N/A')],
                ['Valor FIPE:', f"R$ {valor_medio:.2f}".replace('.', ',')],
            ]
        else:
            # Layout padrão para outros itens
            header_data = [
                ['Código (Material):', codigo or 'N/A'],
                ['Item:', item_name],
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

        header_table = Table(header_data, colWidths=[self.FIRST_COL_WIDTH, self.SECOND_COL_WIDTH])

        # Estilo da tabela de cabeçalho
        header_table_style = [
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8E8E8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), font_bold),
            ('FONTNAME', (1, 0), (1, -1), font_regular),
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

        # ========== PÁGINAS DE COTAÇÕES INDIVIDUAIS (uma por página) ==========
        for idx, source in enumerate(sources):
            story.append(PageBreak())

            # Cabeçalho da página de cotação
            story.extend(self._build_quote_page_header(
                title_style,
                quote_number_style,
                font_bold,
                font_regular,
                idx + 1,
                total_sources
            ))

            story.append(Spacer(1, 6*mm))

            # Tabela com dados da cotação individual
            cot_data = [
                ['Cotação', f"#{idx + 1} de {total_sources}"],
                ['Item', item_name],
                ['Data da Pesquisa', data_pesquisa.strftime('%d/%m/%Y')],
                ['Valor R$', f"R$ {source['price_value']:.2f}".replace('.', ',')],
            ]

            cot_table = Table(cot_data, colWidths=[45*mm, 135*mm])
            cot_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), font_bold),
                ('FONTNAME', (1, 0), (1, -1), font_regular),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            story.append(cot_table)
            story.append(Spacer(1, 4*mm))

            # Link da pesquisa
            story.append(Paragraph("Link", link_title_style))
            story.append(Spacer(1, 2*mm))
            link_text = f'<a href="{source["url"]}">{source["url"]}</a>'
            link_para = Paragraph(link_text, link_style)
            story.append(link_para)
            story.append(Spacer(1, 4*mm))

            # Imagem/Screenshot
            story.append(Paragraph("Imagem", link_title_style))
            story.append(Spacer(1, 2*mm))

            if source.get('screenshot_path'):
                try:
                    # Largura disponível = A4 (210mm) - margens (15mm + 15mm) = 180mm
                    # Altura disponível para imagem (restante da página)
                    content_width = 180*mm
                    content_height = 150*mm  # Altura máxima da imagem
                    img_width = content_width * 0.95  # 95% da largura do conteúdo
                    img = Image(source['screenshot_path'], width=img_width, height=content_height, kind='proportional')
                    story.append(img)
                except Exception as e:
                    story.append(Paragraph(f"[Erro ao carregar imagem: {str(e)}]", styles['Normal']))
            else:
                story.append(Paragraph("[Screenshot não disponível]", styles['Normal']))

        doc.build(story)

    def _build_header(self, title_style, font_bold, font_regular) -> List:
        """
        Constrói o cabeçalho da primeira página com logo e título.
        Logo alinhado à esquerda com 90% da largura da primeira coluna.
        """
        elements = []

        # Calcular tamanho do logo (90% da primeira coluna)
        logo_width = self.FIRST_COL_WIDTH * 0.9

        # Tentar carregar o logo
        logo_element = None
        if os.path.exists(self.LOGO_PATH):
            try:
                logo_element = Image(self.LOGO_PATH, width=logo_width, height=logo_width * 0.4, kind='proportional')
            except Exception as e:
                print(f"Warning: Could not load logo: {e}")

        # Título
        title = Paragraph("Relatório de Cotação de Preços", title_style)

        if logo_element:
            # Criar tabela para alinhar logo à esquerda e título ao lado
            header_table = Table(
                [[logo_element, title]],
                colWidths=[self.FIRST_COL_WIDTH, self.SECOND_COL_WIDTH]
            )
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(header_table)
        else:
            elements.append(title)

        return elements

    def _build_quote_page_header(
        self,
        title_style,
        quote_number_style,
        font_bold,
        font_regular,
        quote_index: int,
        total_quotes: int
    ) -> List:
        """
        Constrói o cabeçalho das páginas de cotação individual.
        Logo à esquerda, título no centro, número da cotação à direita.
        """
        elements = []

        # Calcular tamanho do logo (90% da primeira coluna)
        logo_width = self.FIRST_COL_WIDTH * 0.9

        # Tentar carregar o logo
        logo_element = None
        if os.path.exists(self.LOGO_PATH):
            try:
                logo_element = Image(self.LOGO_PATH, width=logo_width, height=logo_width * 0.4, kind='proportional')
            except Exception as e:
                print(f"Warning: Could not load logo: {e}")

        # Título
        title = Paragraph("Relatório de Cotação de Preços", title_style)

        # Número da cotação
        quote_number = Paragraph(f"Id {quote_index}/{total_quotes}", quote_number_style)

        if logo_element:
            # Criar tabela com 3 colunas: logo | título | número
            header_table = Table(
                [[logo_element, title, quote_number]],
                colWidths=[self.FIRST_COL_WIDTH, 80*mm, 45*mm]
            )
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(header_table)
        else:
            # Sem logo, criar tabela com título e número
            header_table = Table(
                [[title, quote_number]],
                colWidths=[135*mm, 45*mm]
            )
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(header_table)

        return elements

    def _format_date_extenso(self, date: datetime) -> str:
        try:
            weekday = date.strftime('%A')
            day = date.day
            month = date.strftime('%B')
            year = date.year
            return f"{weekday}, {day} de {month} de {year}"
        except:
            return date.strftime('%d/%m/%Y')
