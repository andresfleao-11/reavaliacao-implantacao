"""
Extrator de especificações de páginas de produto.

Camadas de extração (ordem de prioridade):
1. JSON-LD (Schema.org) - Dados estruturados, mais confiável
2. Meta tags (OG, Twitter) - Fallback comum
3. DOM parsing - Último recurso

Reutiliza a infraestrutura do PriceExtractor existente.
"""

import json
import re
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime

from playwright.async_api import Page

from app.models.product_specs import (
    ProductSpecs,
    Dimensions,
    ExtractionMethodSpecs
)


logger = logging.getLogger(__name__)


class SpecExtractor:
    """
    Extrai especificações completas de páginas de produto.

    Uso:
        # Dentro de um contexto PriceExtractor existente
        spec_extractor = SpecExtractor()
        specs = await spec_extractor.extract_specs(page, url)
    """

    # Mapeamento de propriedades para dimensões
    DIMENSION_KEYWORDS = {
        "altura": ["altura", "height", "alto", "h"],
        "largura": ["largura", "width", "largo", "w", "l"],
        "comprimento": ["comprimento", "length", "profundidade", "depth", "fundo", "c", "p"],
    }

    # Mapeamento de propriedades para material
    MATERIAL_KEYWORDS = [
        "material", "matéria-prima", "composição",
        "madeira", "mdf", "mdp", "metal", "aço", "ferro",
        "plástico", "tecido", "couro", "vidro"
    ]

    async def extract_specs(self, page: Page, url: str) -> ProductSpecs:
        """
        Extrai especificações completas da página.

        Args:
            page: Página Playwright já carregada
            url: URL da página

        Returns:
            ProductSpecs com dados extraídos
        """
        # Tentar JSON-LD primeiro (mais confiável)
        specs = await self._try_jsonld_specs(page)
        if specs:
            specs.url_origem = url
            logger.info(f"Specs extraídas via JSON-LD: {specs.nome[:50]}...")
            return specs

        # Fallback para meta tags
        specs = await self._try_meta_specs(page, url)
        if specs:
            logger.info(f"Specs extraídas via META: {specs.nome[:50]}...")
            return specs

        # Fallback para DOM
        specs = await self._try_dom_specs(page, url)
        if specs:
            logger.info(f"Specs extraídas via DOM: {specs.nome[:50]}...")
            return specs

        # Retornar specs mínimas
        logger.warning(f"Não foi possível extrair specs de {url}")
        return ProductSpecs(
            nome="",
            preco=Decimal("0"),
            url_origem=url,
            metodo_extracao=ExtractionMethodSpecs.NOT_EXTRACTED
        )

    async def _try_jsonld_specs(self, page: Page) -> Optional[ProductSpecs]:
        """Extrai specs do JSON-LD Schema.org"""
        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')

            for script in scripts:
                try:
                    content = await script.inner_text()
                    data = json.loads(content)

                    # Pode ser lista ou objeto
                    data_list = data if isinstance(data, list) else [data]

                    for item in data_list:
                        # Procurar Product diretamente ou em @graph
                        if item.get("@type") == "Product":
                            return self._parse_jsonld_product(item)

                        # Verificar @graph (comum em sites VTEX)
                        graph = item.get("@graph", [])
                        for graph_item in graph:
                            if graph_item.get("@type") == "Product":
                                return self._parse_jsonld_product(graph_item)

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"Erro ao processar JSON-LD: {e}")
                    continue

        except Exception as e:
            logger.debug(f"Erro ao buscar JSON-LD: {e}")

        return None

    def _parse_jsonld_product(self, item: dict) -> ProductSpecs:
        """Converte JSON-LD Product em ProductSpecs"""

        # Extrair preço
        offers = item.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        price_str = str(offers.get("price", "0"))
        price_str = price_str.replace(",", ".")
        try:
            price = Decimal(price_str)
        except:
            price = Decimal("0")

        # Extrair marca
        brand = item.get("brand", {})
        marca = None
        if isinstance(brand, dict):
            marca = brand.get("name")
        elif isinstance(brand, str):
            marca = brand

        # Extrair dimensões de additionalProperty
        dimensoes = self._extract_dimensions_from_jsonld(item)

        # Extrair material
        material = self._find_property_value(
            item.get("additionalProperty", []),
            self.MATERIAL_KEYWORDS
        )

        # Extrair cor
        cor = self._find_property_value(
            item.get("additionalProperty", []),
            ["cor", "color", "colour"]
        )

        # Extrair todas as propriedades
        especificacoes = self._extract_all_properties(item)

        return ProductSpecs(
            nome=item.get("name", ""),
            preco=price,
            url_origem="",
            marca=marca,
            modelo=item.get("model"),
            sku=item.get("sku"),
            dimensoes=dimensoes,
            material=material,
            cor=cor,
            especificacoes=especificacoes,
            metodo_extracao=ExtractionMethodSpecs.JSONLD,
            raw_jsonld=item
        )

    def _extract_dimensions_from_jsonld(self, item: dict) -> Optional[Dimensions]:
        """Extrai dimensões do JSON-LD additionalProperty"""
        props = item.get("additionalProperty", [])

        if not props:
            return None

        dimensoes = Dimensions()
        found_any = False

        for prop in props:
            if not isinstance(prop, dict):
                continue

            name = str(prop.get("name", "")).lower()
            value = str(prop.get("value", ""))

            if not value:
                continue

            # Verificar qual dimensão é
            for dim_attr, keywords in self.DIMENSION_KEYWORDS.items():
                if any(kw in name for kw in keywords):
                    metros = Dimensions.parse_dimension_value(value)
                    if metros:
                        setattr(dimensoes, dim_attr, metros)
                        found_any = True
                    break

        return dimensoes if found_any else None

    def _find_property_value(
        self,
        properties: List[Dict],
        keywords: List[str]
    ) -> Optional[str]:
        """Encontra valor de uma propriedade por palavras-chave"""
        for prop in properties:
            if not isinstance(prop, dict):
                continue

            name = str(prop.get("name", "")).lower()
            value = prop.get("value")

            if any(kw in name for kw in keywords):
                return str(value) if value else None

        return None

    def _extract_all_properties(self, item: dict) -> Dict[str, Any]:
        """Extrai todas as propriedades adicionais"""
        props = item.get("additionalProperty", [])
        result = {}

        for prop in props:
            if not isinstance(prop, dict):
                continue

            name = prop.get("name")
            value = prop.get("value")

            if name and value:
                result[str(name)] = value

        # Adicionar campos diretos relevantes
        direct_fields = ["category", "description", "weight", "color"]
        for field in direct_fields:
            if field in item and item[field]:
                result[field] = item[field]

        return result

    async def _try_meta_specs(self, page: Page, url: str) -> Optional[ProductSpecs]:
        """Extrai specs de meta tags"""
        try:
            # Nome do produto
            nome = await self._get_meta_content(page, [
                'meta[property="og:title"]',
                'meta[name="twitter:title"]',
                'title'
            ])

            if not nome:
                return None

            # Preço
            preco_str = await self._get_meta_content(page, [
                'meta[property="product:price:amount"]',
                'meta[property="og:price:amount"]',
            ])

            try:
                preco = Decimal(str(preco_str).replace(",", ".")) if preco_str else Decimal("0")
            except:
                preco = Decimal("0")

            # Descrição (pode conter specs)
            descricao = await self._get_meta_content(page, [
                'meta[property="og:description"]',
                'meta[name="description"]',
            ])

            # Tentar extrair dimensões da descrição
            dimensoes = None
            if descricao:
                dimensoes = self._extract_dimensions_from_text(descricao)

            return ProductSpecs(
                nome=nome,
                preco=preco,
                url_origem=url,
                dimensoes=dimensoes,
                especificacoes={"descricao": descricao} if descricao else {},
                metodo_extracao=ExtractionMethodSpecs.META
            )

        except Exception as e:
            logger.debug(f"Erro ao extrair meta specs: {e}")
            return None

    async def _get_meta_content(self, page: Page, selectors: List[str]) -> Optional[str]:
        """Obtém conteúdo do primeiro meta tag encontrado"""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Para tag title, pegar innerText
                    if selector == 'title':
                        return await element.inner_text()
                    # Para meta tags, pegar content
                    content = await element.get_attribute("content")
                    if content:
                        return content.strip()
            except:
                continue
        return None

    async def _try_dom_specs(self, page: Page, url: str) -> Optional[ProductSpecs]:
        """Extrai specs via DOM parsing"""
        try:
            # Nome do produto
            nome = await self._extract_product_name(page)
            if not nome:
                return None

            # Preço
            preco = await self._extract_price_from_dom(page)

            # Especificações técnicas
            specs = await self._extract_specs_table(page)

            # Tentar extrair dimensões das specs ou do nome
            dimensoes = None
            if specs:
                dimensoes = self._extract_dimensions_from_specs(specs)
            if not dimensoes and nome:
                dimensoes = self._extract_dimensions_from_text(nome)

            # Extrair material das specs
            material = None
            if specs:
                for key, value in specs.items():
                    if any(kw in key.lower() for kw in self.MATERIAL_KEYWORDS):
                        material = str(value)
                        break

            return ProductSpecs(
                nome=nome,
                preco=preco,
                url_origem=url,
                dimensoes=dimensoes,
                material=material,
                especificacoes=specs,
                metodo_extracao=ExtractionMethodSpecs.DOM
            )

        except Exception as e:
            logger.debug(f"Erro ao extrair DOM specs: {e}")
            return None

    async def _extract_product_name(self, page: Page) -> Optional[str]:
        """Extrai nome do produto via DOM"""
        selectors = [
            'h1[class*="product"]',
            'h1[class*="title"]',
            'h1[data-testid*="product"]',
            '.product-name h1',
            '.product-title',
            'h1',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text) > 3:
                        return text.strip()
            except:
                continue

        return None

    async def _extract_price_from_dom(self, page: Page) -> Decimal:
        """Extrai preço via DOM"""
        selectors = [
            '[data-testid*="price"]',
            '[class*="price"]',
            '[id*="price"]',
            '.price-tag',
            '.product-price',
            'span[itemprop="price"]',
        ]

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if "R$" in text or "," in text:
                        price = self._parse_price_text(text)
                        if price and price > Decimal("1"):
                            return price
            except:
                continue

        return Decimal("0")

    def _parse_price_text(self, text: str) -> Optional[Decimal]:
        """Converte texto de preço para Decimal"""
        text = text.strip()
        text = re.sub(r'[^\d,.]', '', text)

        if not text:
            return None

        # Normalizar formato brasileiro
        if ',' in text and '.' in text:
            if text.rfind(',') > text.rfind('.'):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            if text.count(',') == 1 and len(text.split(',')[1]) == 2:
                text = text.replace(',', '.')
            else:
                text = text.replace(',', '')

        try:
            return Decimal(text)
        except:
            return None

    async def _extract_specs_table(self, page: Page) -> Dict[str, Any]:
        """Extrai especificações de tabelas/listas"""
        specs = {}

        # Padrões comuns de tabela de specs
        table_selectors = [
            'table[class*="spec"]',
            'table[class*="ficha"]',
            '.specifications table',
            '.product-specs table',
            '[data-testid*="spec"] table',
        ]

        for selector in table_selectors:
            try:
                table = await page.query_selector(selector)
                if table:
                    rows = await table.query_selector_all("tr")
                    for row in rows:
                        cells = await row.query_selector_all("td, th")
                        if len(cells) >= 2:
                            key = await cells[0].inner_text()
                            value = await cells[1].inner_text()
                            if key and value:
                                specs[key.strip()] = value.strip()
            except:
                continue

        # Tentar listas de especificações (dl, ul)
        list_selectors = [
            'dl[class*="spec"]',
            '.specifications dl',
            'ul[class*="spec"]',
        ]

        for selector in list_selectors:
            try:
                dl = await page.query_selector(selector)
                if dl:
                    dts = await dl.query_selector_all("dt")
                    dds = await dl.query_selector_all("dd")
                    for dt, dd in zip(dts, dds):
                        key = await dt.inner_text()
                        value = await dd.inner_text()
                        if key and value:
                            specs[key.strip()] = value.strip()
            except:
                continue

        return specs

    def _extract_dimensions_from_specs(self, specs: Dict[str, Any]) -> Optional[Dimensions]:
        """Extrai dimensões de um dicionário de specs"""
        dimensoes = Dimensions()
        found_any = False

        for key, value in specs.items():
            key_lower = key.lower()

            for dim_attr, keywords in self.DIMENSION_KEYWORDS.items():
                if any(kw in key_lower for kw in keywords):
                    metros = Dimensions.parse_dimension_value(str(value))
                    if metros:
                        setattr(dimensoes, dim_attr, metros)
                        found_any = True
                    break

        return dimensoes if found_any else None

    def _extract_dimensions_from_text(self, text: str) -> Optional[Dimensions]:
        """Extrai dimensões de texto livre (ex: "Mesa 2,40m x 1,20m")"""
        dimensoes = Dimensions()

        # Padrão: NxMxP (largura x comprimento x altura)
        pattern = r'(\d+[,.]?\d*)\s*(m|cm|mm)?\s*[xX×]\s*(\d+[,.]?\d*)\s*(m|cm|mm)?(?:\s*[xX×]\s*(\d+[,.]?\d*)\s*(m|cm|mm)?)?'

        match = re.search(pattern, text)
        if match:
            dim1 = Dimensions.parse_dimension_value(f"{match.group(1)}{match.group(2) or 'm'}")
            dim2 = Dimensions.parse_dimension_value(f"{match.group(3)}{match.group(4) or 'm'}")

            if dim1 and dim2:
                # Assumir: maior = comprimento, menor = largura
                if dim1 >= dim2:
                    dimensoes.comprimento = dim1
                    dimensoes.largura = dim2
                else:
                    dimensoes.comprimento = dim2
                    dimensoes.largura = dim1

                # Terceira dimensão (altura)
                if match.group(5):
                    dim3 = Dimensions.parse_dimension_value(
                        f"{match.group(5)}{match.group(6) or 'm'}"
                    )
                    if dim3:
                        dimensoes.altura = dim3

                return dimensoes

        # Padrão simples: apenas um número com unidade
        simple_pattern = r'(\d+[,.]?\d*)\s*(metros?|m)\b'
        simple_match = re.search(simple_pattern, text.lower())
        if simple_match:
            metros = Dimensions.parse_dimension_value(f"{simple_match.group(1)}m")
            if metros:
                dimensoes.comprimento = metros
                return dimensoes

        return None
