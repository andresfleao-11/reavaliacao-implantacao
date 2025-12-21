"""
Estruturas de dados para especificações de produtos extraídas de páginas.
Usado para validação query vs specs e cálculo de metro linear.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from decimal import Decimal
import re


class ExtractionMethodSpecs(str, Enum):
    """Método usado para extrair especificações da página"""
    JSONLD = "jsonld"
    META = "meta"
    DOM = "dom"
    JSONLD_PLAYWRIGHT = "jsonld_playwright"
    NOT_EXTRACTED = "not_extracted"


@dataclass
class Dimensions:
    """Dimensões físicas do produto em metros"""
    altura: Optional[float] = None
    largura: Optional[float] = None
    comprimento: Optional[float] = None
    profundidade: Optional[float] = None

    @property
    def metro_linear(self) -> Optional[float]:
        """Retorna a medida principal (comprimento ou largura)"""
        return self.comprimento or self.largura

    def is_valid(self) -> bool:
        """Verifica se há pelo menos uma dimensão válida"""
        return any([self.altura, self.largura, self.comprimento, self.profundidade])

    def to_dict(self) -> Dict[str, Optional[float]]:
        """Converte para dicionário"""
        return {
            "altura": self.altura,
            "largura": self.largura,
            "comprimento": self.comprimento,
            "profundidade": self.profundidade
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Dimensions":
        """Cria Dimensions a partir de dicionário"""
        if not data:
            return cls()
        return cls(
            altura=data.get("altura"),
            largura=data.get("largura"),
            comprimento=data.get("comprimento"),
            profundidade=data.get("profundidade")
        )

    @staticmethod
    def parse_dimension_value(value: str) -> Optional[float]:
        """
        Converte valor de dimensão para metros.
        Suporta: "2.40m", "240cm", "2400mm", "2,40 m", "2.40"
        """
        if not value:
            return None

        value = str(value).lower().strip()
        value = value.replace(" ", "").replace(",", ".")

        # Tentar extrair número e unidade
        match = re.match(r"([\d.]+)\s*(m|cm|mm|metros?|centimetros?|milimetros?)?", value)
        if not match:
            return None

        try:
            numero = float(match.group(1))
        except ValueError:
            return None

        unidade = match.group(2) or "m"

        # Converter para metros
        if "cm" in unidade or "centimetro" in unidade:
            return numero / 100
        elif "mm" in unidade or "milimetro" in unidade:
            return numero / 1000
        else:
            # Heurística: se número > 100, provavelmente está em cm
            if numero > 100:
                return numero / 100
            return numero


@dataclass
class ProductSpecs:
    """Especificações completas de um produto extraídas da página"""

    # Campos obrigatórios
    nome: str
    preco: Decimal
    url_origem: str

    # Metadados de extração
    timestamp: datetime = field(default_factory=datetime.now)
    metodo_extracao: ExtractionMethodSpecs = ExtractionMethodSpecs.NOT_EXTRACTED
    js_rendered: bool = False

    # Campos opcionais extraídos
    marca: Optional[str] = None
    modelo: Optional[str] = None
    sku: Optional[str] = None

    # Dimensões
    dimensoes: Optional[Dimensions] = None

    # Material e características
    material: Optional[str] = None
    cor: Optional[str] = None

    # Especificações técnicas genéricas
    especificacoes: Dict[str, Any] = field(default_factory=dict)

    # Dados brutos do JSON-LD (para debug)
    raw_jsonld: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário (para serialização JSON)"""
        return {
            "nome": self.nome,
            "preco": str(self.preco),
            "url_origem": self.url_origem,
            "timestamp": self.timestamp.isoformat(),
            "metodo_extracao": self.metodo_extracao.value,
            "js_rendered": self.js_rendered,
            "marca": self.marca,
            "modelo": self.modelo,
            "sku": self.sku,
            "dimensoes": self.dimensoes.to_dict() if self.dimensoes else None,
            "material": self.material,
            "cor": self.cor,
            "especificacoes": self.especificacoes
        }

    def has_dimensions(self) -> bool:
        """Verifica se o produto tem dimensões extraídas"""
        return self.dimensoes is not None and self.dimensoes.is_valid()


@dataclass
class SpecMatchResult:
    """Resultado da comparação query vs specs"""
    is_match: bool
    confidence: float  # 0.0 a 1.0

    # Detalhes da comparação
    tipo_match: bool = True
    material_match: bool = True
    dimensao_match: bool = True

    # Motivo de falha (se houver)
    failure_reason: Optional[str] = None

    # Detalhes para log
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            "is_match": self.is_match,
            "confidence": self.confidence,
            "tipo_match": self.tipo_match,
            "material_match": self.material_match,
            "dimensao_match": self.dimensao_match,
            "failure_reason": self.failure_reason,
            "details": self.details
        }


@dataclass
class LinearMeterResult:
    """Resultado do cálculo de metro linear"""
    produtos_base: List[ProductSpecs]
    precos_por_metro: List[float]
    media_metro: float
    comprimento_alvo: float  # Dimensão original do bem
    valor_calculado: Decimal

    # Metodologia para relatório
    metodologia: str = ""

    def gerar_metodologia(self) -> str:
        """Gera texto explicativo para o PDF"""
        linhas = [
            "METODOLOGIA: Proporcionalidade por Metro Linear",
            "",
            f"Comprimento do bem original: {self.comprimento_alvo:.2f}m",
            f"Produtos utilizados como base: {len(self.produtos_base)}",
            "",
            "Cálculo do metro linear médio:"
        ]

        for i, (prod, preco_m) in enumerate(zip(self.produtos_base, self.precos_por_metro), 1):
            dim = prod.dimensoes.metro_linear if prod.dimensoes else "N/A"
            nome_truncado = prod.nome[:50] + "..." if len(prod.nome) > 50 else prod.nome
            linhas.append(
                f"  {i}. {nome_truncado} - R$ {prod.preco:.2f} / {dim}m = R$ {preco_m:.2f}/m"
            )

        linhas.extend([
            "",
            f"Média: R$ {self.media_metro:.2f}/metro",
            f"Valor calculado: {self.comprimento_alvo:.2f}m x R$ {self.media_metro:.2f} = R$ {self.valor_calculado:.2f}",
            "",
            "Base normativa: NBC TSP 07 / MCASP - Valor justo de reposição"
        ])

        self.metodologia = "\n".join(linhas)
        return self.metodologia

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            "produtos_base_count": len(self.produtos_base),
            "precos_por_metro": self.precos_por_metro,
            "media_metro": self.media_metro,
            "comprimento_alvo": self.comprimento_alvo,
            "valor_calculado": str(self.valor_calculado),
            "metodologia": self.metodologia
        }
