"""
Calculador de valor por Metro Linear.

Usado quando:
- Bem tem dimensões não-padrão (ex: mesa 4,50m)
- Não foram encontrados produtos com dimensões similares
- Categoria suporta cálculo proporcional (mesas, bancadas, sofás)

Base normativa: NBC TSP 07 / MCASP - Valor justo de reposição por proporcionalidade.
"""

import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean, stdev

from app.models.product_specs import ProductSpecs, LinearMeterResult


logger = logging.getLogger(__name__)


class LinearMeterCalculator:
    """
    Calcula valor de bens por proporcionalidade de metro linear.

    Fluxo:
    1. Filtrar produtos com dimensões válidas
    2. Calcular preço/metro para cada produto
    3. Remover outliers estatísticos
    4. Calcular média
    5. Aplicar proporcionalidade ao comprimento original
    6. Gerar metodologia para relatório

    Uso:
        calculator = LinearMeterCalculator()
        if calculator.can_apply(query_specs):
            result = calculator.calculate(
                produtos=produtos_encontrados,
                comprimento_alvo=4.50
            )
            print(f"Valor calculado: R$ {result.valor_calculado}")
            print(result.metodologia)
    """

    # Categorias que suportam cálculo de metro linear
    CATEGORIAS_SUPORTADAS = [
        "mesa", "bancada", "balcão", "balcao",
        "prateleira", "estante", "sofá", "sofa",
        "rack", "aparador", "credenza"
    ]

    # Mínimo de produtos para cálculo confiável
    MIN_PRODUTOS = 2

    # Desvios padrão para considerar outlier
    OUTLIER_THRESHOLD = 2.0

    def __init__(
        self,
        min_produtos: int = None,
        outlier_threshold: float = None,
        remover_outliers: bool = True
    ):
        """
        Args:
            min_produtos: Mínimo de produtos com dimensões para cálculo
            outlier_threshold: Número de desvios padrão para outlier
            remover_outliers: Se deve remover outliers do cálculo
        """
        self.min_produtos = min_produtos or self.MIN_PRODUTOS
        self.outlier_threshold = outlier_threshold or self.OUTLIER_THRESHOLD
        self.remover_outliers = remover_outliers

    def can_apply(self, query_specs: Dict[str, Any]) -> bool:
        """
        Verifica se o cálculo de metro linear é aplicável.

        Args:
            query_specs: Especificações da query (bem_patrimonial)

        Returns:
            True se metro linear pode ser usado
        """
        tipo_bem = str(query_specs.get("tipo_bem", "")).lower()

        # Verificar se a categoria suporta metro linear
        categoria_suportada = any(
            cat in tipo_bem for cat in self.CATEGORIAS_SUPORTADAS
        )

        if not categoria_suportada:
            return False

        # Verificar se há dimensões na query
        dimensoes = query_specs.get("dimensoes", {})
        if not dimensoes:
            return False

        # Verificar se tem comprimento ou largura
        tem_dimensao_linear = (
            dimensoes.get("comprimento") or
            dimensoes.get("largura")
        )

        return tem_dimensao_linear

    def get_comprimento_alvo(self, query_specs: Dict[str, Any]) -> Optional[float]:
        """
        Extrai o comprimento/medida linear alvo da query.

        Args:
            query_specs: Especificações da query

        Returns:
            Comprimento em metros ou None
        """
        dimensoes = query_specs.get("dimensoes", {})
        return dimensoes.get("comprimento") or dimensoes.get("largura")

    def calculate(
        self,
        produtos: List[ProductSpecs],
        comprimento_alvo: float
    ) -> LinearMeterResult:
        """
        Calcula valor por metro linear.

        Args:
            produtos: Lista de produtos encontrados
            comprimento_alvo: Comprimento do bem original em metros

        Returns:
            LinearMeterResult com valor calculado e metodologia

        Raises:
            ValueError: Se não houver produtos válidos suficientes
        """
        # 1. Filtrar produtos com dimensões válidas
        produtos_validos = self._filter_products_with_dimensions(produtos)

        if len(produtos_validos) < self.min_produtos:
            raise ValueError(
                f"Insuficiente: {len(produtos_validos)} produtos com dimensões, "
                f"mínimo necessário: {self.min_produtos}"
            )

        # 2. Calcular preço por metro para cada produto
        precos_por_metro = []
        produtos_usados = []

        for prod in produtos_validos:
            metro = prod.dimensoes.metro_linear
            if metro and metro > 0:
                preco_m = float(prod.preco) / metro
                precos_por_metro.append(preco_m)
                produtos_usados.append(prod)

        if not precos_por_metro:
            raise ValueError("Nenhum produto com dimensões e preço válidos")

        logger.info(
            f"Metro linear: {len(precos_por_metro)} produtos, "
            f"preços/m: {[f'R${p:.2f}' for p in precos_por_metro]}"
        )

        # 3. Remover outliers se configurado e houver dados suficientes
        if self.remover_outliers and len(precos_por_metro) >= 3:
            precos_por_metro, produtos_usados = self._remove_outliers(
                precos_por_metro, produtos_usados
            )

        if not precos_por_metro:
            raise ValueError("Todos os produtos foram removidos como outliers")

        # 4. Calcular média
        media_metro = mean(precos_por_metro)

        # 5. Aplicar proporcionalidade
        valor_calculado = Decimal(str(media_metro * comprimento_alvo))
        valor_calculado = valor_calculado.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        logger.info(
            f"Metro linear calculado: média R${media_metro:.2f}/m, "
            f"alvo {comprimento_alvo}m = R${valor_calculado}"
        )

        # 6. Criar resultado
        result = LinearMeterResult(
            produtos_base=produtos_usados,
            precos_por_metro=precos_por_metro,
            media_metro=media_metro,
            comprimento_alvo=comprimento_alvo,
            valor_calculado=valor_calculado
        )

        # 7. Gerar metodologia para relatório
        result.gerar_metodologia()

        return result

    def _filter_products_with_dimensions(
        self,
        produtos: List[ProductSpecs]
    ) -> List[ProductSpecs]:
        """Filtra produtos que têm dimensões válidas"""
        return [
            p for p in produtos
            if (
                p.dimensoes and
                p.dimensoes.metro_linear and
                p.dimensoes.metro_linear > 0 and
                p.preco and
                p.preco > 0
            )
        ]

    def _remove_outliers(
        self,
        precos: List[float],
        produtos: List[ProductSpecs]
    ) -> tuple[List[float], List[ProductSpecs]]:
        """
        Remove outliers estatísticos (preços muito fora da média).

        Usa método de desvio padrão: remove valores > threshold * σ da média.
        """
        if len(precos) < 3:
            return precos, produtos

        media = mean(precos)
        desvio = stdev(precos)

        if desvio == 0:
            return precos, produtos

        precos_filtrados = []
        produtos_filtrados = []

        for preco, prod in zip(precos, produtos):
            z_score = abs(preco - media) / desvio

            if z_score <= self.outlier_threshold:
                precos_filtrados.append(preco)
                produtos_filtrados.append(prod)
            else:
                logger.info(
                    f"Outlier removido: R${preco:.2f}/m (z-score={z_score:.2f})"
                )

        # Garantir que não removemos tudo
        if len(precos_filtrados) < self.min_produtos:
            logger.warning(
                f"Muito outliers removidos, mantendo dados originais. "
                f"De {len(precos)} para {len(precos_filtrados)}"
            )
            return precos, produtos

        return precos_filtrados, produtos_filtrados

    def estimate_with_fallback(
        self,
        query_specs: Dict[str, Any],
        produtos: List[ProductSpecs],
        preco_medio_mercado: Optional[Decimal] = None
    ) -> Optional[LinearMeterResult]:
        """
        Tenta calcular metro linear com fallbacks.

        Se não houver dimensões suficientes nos produtos,
        usa estimativas baseadas no preço médio de mercado.

        Args:
            query_specs: Especificações da query
            produtos: Produtos encontrados
            preco_medio_mercado: Preço médio como fallback

        Returns:
            LinearMeterResult ou None se não for possível
        """
        if not self.can_apply(query_specs):
            return None

        comprimento_alvo = self.get_comprimento_alvo(query_specs)
        if not comprimento_alvo:
            return None

        try:
            return self.calculate(produtos, comprimento_alvo)
        except ValueError as e:
            logger.warning(f"Metro linear falhou: {e}")

            # Fallback: estimar baseado no preço médio
            if preco_medio_mercado and preco_medio_mercado > 0:
                # Assumir produto de referência com 1.5m (tamanho comum)
                ref_comprimento = 1.5
                preco_por_metro = float(preco_medio_mercado) / ref_comprimento
                valor_calculado = Decimal(str(preco_por_metro * comprimento_alvo))
                valor_calculado = valor_calculado.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                logger.info(
                    f"Metro linear estimado (fallback): R${valor_calculado} "
                    f"baseado em preço médio R${preco_medio_mercado}"
                )

                result = LinearMeterResult(
                    produtos_base=[],
                    precos_por_metro=[preco_por_metro],
                    media_metro=preco_por_metro,
                    comprimento_alvo=comprimento_alvo,
                    valor_calculado=valor_calculado
                )

                result.metodologia = (
                    "METODOLOGIA: Estimativa por Metro Linear (Fallback)\n\n"
                    f"Comprimento do bem original: {comprimento_alvo:.2f}m\n"
                    f"Preço médio de referência: R$ {preco_medio_mercado:.2f}\n"
                    f"Comprimento de referência assumido: {ref_comprimento}m\n"
                    f"Preço por metro estimado: R$ {preco_por_metro:.2f}/m\n\n"
                    f"Valor calculado: {comprimento_alvo:.2f}m x R$ {preco_por_metro:.2f} "
                    f"= R$ {valor_calculado:.2f}\n\n"
                    "NOTA: Cálculo estimativo. Produtos de referência não possuíam "
                    "dimensões especificadas.\n"
                    "Base normativa: NBC TSP 07 / MCASP"
                )

                return result

            return None
