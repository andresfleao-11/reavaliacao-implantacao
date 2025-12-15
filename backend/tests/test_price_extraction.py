import pytest
from app.services.price_extractor import PriceExtractor
from decimal import Decimal


class TestPriceExtractor:
    def setup_method(self):
        self.extractor = PriceExtractor()

    def test_parse_price_with_comma_decimal(self):
        assert self.extractor._parse_price("R$ 1.234,56") == Decimal("1234.56")

    def test_parse_price_with_dot_thousands(self):
        assert self.extractor._parse_price("1.234,50") == Decimal("1234.50")

    def test_parse_price_simple(self):
        assert self.extractor._parse_price("123,45") == Decimal("123.45")

    def test_parse_price_no_decimals(self):
        assert self.extractor._parse_price("1234") == Decimal("1234")

    def test_parse_price_invalid(self):
        assert self.extractor._parse_price("abc") is None

    def test_parse_price_mixed_separators(self):
        assert self.extractor._parse_price("1.234.567,89") == Decimal("1234567.89")

    def test_find_price_in_text(self):
        text = "O produto custa R$ 459,90 com frete grátis"
        price = self.extractor._find_price_in_text(text)
        assert price == Decimal("459.90")

    def test_find_price_in_text_multiple(self):
        text = "De R$ 999,00 por R$ 599,90"
        price = self.extractor._find_price_in_text(text)
        assert price in [Decimal("999.00"), Decimal("599.90")]

    def test_find_price_in_text_no_price(self):
        text = "Este produto está esgotado"
        price = self.extractor._find_price_in_text(text)
        assert price is None
