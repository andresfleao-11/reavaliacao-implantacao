import pytest
from app.services.pdf_generator import PDFGenerator
from datetime import datetime
from decimal import Decimal
import os
import tempfile


class TestPDFGenerator:
    def setup_method(self):
        self.generator = PDFGenerator()

    def test_generate_quote_pdf(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            output_path = tmp.name

        try:
            sources = [
                {
                    'url': 'https://example.com/product1',
                    'price_value': Decimal('599.90'),
                    'screenshot_path': None
                },
                {
                    'url': 'https://example.com/product2',
                    'price_value': Decimal('649.00'),
                    'screenshot_path': None
                },
                {
                    'url': 'https://example.com/product3',
                    'price_value': Decimal('579.50'),
                    'screenshot_path': None
                }
            ]

            self.generator.generate_quote_pdf(
                output_path=output_path,
                item_name='Tacômetro Foto Digital',
                codigo='100002346',
                sources=sources,
                valor_medio=Decimal('609.47'),
                local='Online',
                pesquisador='Sistema',
                data_pesquisa=datetime.now()
            )

            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_format_date_extenso(self):
        date = datetime(2025, 10, 8, 14, 30)
        formatted = self.generator._format_date_extenso(date)
        assert isinstance(formatted, str)
        assert '8' in formatted
        assert '2025' in formatted
