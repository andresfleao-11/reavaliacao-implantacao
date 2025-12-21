"""
Validador de especificações: Query vs Produto encontrado.

Hierarquia de validação:
1. Tipo do bem (obrigatório) - mesa é mesa, cadeira é cadeira
2. Material (se especificado) - MDF é MDF, aço é aço
3. Dimensões (com tolerância) - se query pede 2m, aceitar 1.6m a 2.4m
"""

import logging
from typing import Dict, Any, List, Optional

from app.models.product_specs import ProductSpecs, Dimensions, SpecMatchResult


logger = logging.getLogger(__name__)


class SpecValidator:
    """
    Valida se um produto encontrado corresponde à query de busca.

    Uso:
        validator = SpecValidator()
        result = validator.validate(
            query_specs=analysis_result.bem_patrimonial,
            product_specs=extracted_specs
        )
        if not result.is_match:
            # Rejeitar produto
    """

    # Tolerância para dimensões (20%)
    TOLERANCIA_DIMENSAO = 0.20

    # Sinônimos de tipos de bens
    TIPO_SINONIMOS = {
        "mesa": ["mesa", "table", "desk", "bancada", "escrivaninha"],
        "cadeira": ["cadeira", "chair", "assento", "banco"],
        "poltrona": ["poltrona", "armchair", "sofá 1 lugar"],
        "armario": ["armário", "armario", "cabinet", "gaveteiro", "arquivo"],
        "estante": ["estante", "prateleira", "shelf", "rack", "modular"],
        "sofa": ["sofá", "sofa", "divã", "recamier"],
        "notebook": ["notebook", "laptop", "computador portátil", "ultrabook"],
        "desktop": ["desktop", "computador", "pc", "workstation"],
        "monitor": ["monitor", "tela", "display", "screen"],
        "impressora": ["impressora", "multifuncional", "printer"],
        "ar_condicionado": ["ar-condicionado", "ar condicionado", "split", "climatizador"],
        "geladeira": ["geladeira", "refrigerador", "frigobar", "freezer"],
        "microondas": ["microondas", "micro-ondas", "forno elétrico"],
    }

    # Sinônimos de materiais
    MATERIAL_SINONIMOS = {
        "mdf": ["mdf", "mdp", "aglomerado", "compensado"],
        "madeira": ["madeira", "wood", "maciça", "compensado"],
        "metal": ["metal", "aço", "ferro", "alumínio", "inox", "cromado"],
        "plastico": ["plástico", "polipropileno", "abs", "pvc"],
        "vidro": ["vidro", "glass", "cristal", "temperado"],
        "tecido": ["tecido", "fabric", "pano", "lona", "nylon"],
        "couro": ["couro", "leather", "courino", "sintético", "pu"],
    }

    def __init__(
        self,
        tolerancia_dimensao: float = None,
        validar_tipo: bool = True,
        validar_material: bool = True,
        validar_dimensoes: bool = True
    ):
        """
        Args:
            tolerancia_dimensao: Tolerância percentual para dimensões (default 20%)
            validar_tipo: Se deve validar tipo do bem
            validar_material: Se deve validar material
            validar_dimensoes: Se deve validar dimensões
        """
        self.tolerancia_dimensao = tolerancia_dimensao or self.TOLERANCIA_DIMENSAO
        self.validar_tipo = validar_tipo
        self.validar_material = validar_material
        self.validar_dimensoes = validar_dimensoes

    def validate(
        self,
        query_specs: Dict[str, Any],
        product_specs: ProductSpecs
    ) -> SpecMatchResult:
        """
        Valida correspondência entre query e produto.

        Args:
            query_specs: Especificações da query (do ItemAnalysisResult.bem_patrimonial)
            product_specs: Especificações extraídas da página

        Returns:
            SpecMatchResult com detalhes da validação
        """
        result = SpecMatchResult(is_match=True, confidence=1.0, details={})

        # 1. Validar tipo do bem (obrigatório)
        if self.validar_tipo:
            tipo_result = self._validate_tipo(query_specs, product_specs)
            result.tipo_match = tipo_result
            result.details["tipo"] = {
                "query": query_specs.get("tipo_bem", ""),
                "product": product_specs.nome[:100],
                "match": tipo_result
            }

            if not tipo_result:
                result.is_match = False
                result.failure_reason = "spec_mismatch_type"
                result.confidence = 0.0
                logger.info(
                    f"Tipo não corresponde: query={query_specs.get('tipo_bem')} "
                    f"vs produto={product_specs.nome[:50]}"
                )
                return result

        # 2. Validar material (se especificado)
        if self.validar_material:
            material_result = self._validate_material(query_specs, product_specs)
            result.material_match = material_result
            result.details["material"] = {
                "query": query_specs.get("material", ""),
                "product": product_specs.material,
                "match": material_result
            }

            if not material_result:
                result.is_match = False
                result.failure_reason = "spec_mismatch_material"
                result.confidence *= 0.5
                logger.info(
                    f"Material não corresponde: query={query_specs.get('material')} "
                    f"vs produto={product_specs.material}"
                )

        # 3. Validar dimensões (se especificadas)
        if self.validar_dimensoes:
            dimensao_result, dimensao_details = self._validate_dimensoes(
                query_specs, product_specs
            )
            result.dimensao_match = dimensao_result
            result.details["dimensoes"] = dimensao_details

            if not dimensao_result:
                result.is_match = False
                if not result.failure_reason:
                    result.failure_reason = "spec_mismatch_dimension"
                result.confidence *= 0.7
                logger.info(
                    f"Dimensões fora da tolerância: "
                    f"query={query_specs.get('dimensoes')} "
                    f"vs produto={product_specs.dimensoes}"
                )

        # Log do resultado final
        if result.is_match:
            logger.debug(
                f"Validação OK: {product_specs.nome[:50]} "
                f"(confidence={result.confidence:.2f})"
            )
        else:
            logger.info(
                f"Validação FALHOU: {product_specs.nome[:50]} "
                f"(reason={result.failure_reason})"
            )

        return result

    def _validate_tipo(
        self,
        query: Dict[str, Any],
        product: ProductSpecs
    ) -> bool:
        """Valida se o tipo do bem corresponde"""
        query_tipo = str(query.get("tipo_bem", "")).lower().strip()

        if not query_tipo:
            return True  # Não especificado = aceita qualquer

        product_nome = product.nome.lower()
        product_desc = str(product.especificacoes.get("descricao", "")).lower()
        product_text = f"{product_nome} {product_desc}"

        # Verificar correspondência direta
        if query_tipo in product_text:
            return True

        # Verificar sinônimos
        for tipo_base, sinonimos in self.TIPO_SINONIMOS.items():
            query_is_this_type = any(s in query_tipo for s in sinonimos)
            product_is_this_type = any(s in product_text for s in sinonimos)

            if query_is_this_type and product_is_this_type:
                return True

        return False

    def _validate_material(
        self,
        query: Dict[str, Any],
        product: ProductSpecs
    ) -> bool:
        """Valida se o material corresponde"""
        query_material = str(query.get("material", "")).lower().strip()

        if not query_material:
            return True  # Não especificado = aceita qualquer

        # Verificar no campo material do produto
        product_material = str(product.material or "").lower()
        product_nome = product.nome.lower()
        product_specs_text = str(product.especificacoes).lower()

        combined_text = f"{product_material} {product_nome} {product_specs_text}"

        # Correspondência direta
        if query_material in combined_text:
            return True

        # Verificar sinônimos
        for material_base, sinonimos in self.MATERIAL_SINONIMOS.items():
            query_is_this_material = any(s in query_material for s in sinonimos)
            product_is_this_material = any(s in combined_text for s in sinonimos)

            if query_is_this_material and product_is_this_material:
                return True

        return False

    def _validate_dimensoes(
        self,
        query: Dict[str, Any],
        product: ProductSpecs
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Valida se as dimensões estão dentro da tolerância.

        Returns:
            Tuple[bool, dict]: (is_valid, details)
        """
        query_dim = query.get("dimensoes", {})
        details = {
            "query_dimensoes": query_dim,
            "product_dimensoes": product.dimensoes.to_dict() if product.dimensoes else None,
            "tolerancia": self.tolerancia_dimensao,
            "validacoes": []
        }

        if not query_dim:
            return True, details  # Não especificado = aceita qualquer

        if not product.dimensoes:
            # Query tem dimensões, produto não tem
            details["validacoes"].append({
                "campo": "dimensoes",
                "resultado": "skip",
                "motivo": "Produto sem dimensões extraídas"
            })
            return True, details  # Não falhar se não conseguiu extrair

        # Construir Dimensions da query se for dict
        if isinstance(query_dim, dict):
            query_dimensions = Dimensions.from_dict(query_dim)
        else:
            query_dimensions = query_dim

        # Validar comprimento/metro linear principal
        query_comprimento = query_dimensions.metro_linear
        product_comprimento = product.dimensoes.metro_linear

        if query_comprimento and product_comprimento:
            tolerancia = query_comprimento * self.tolerancia_dimensao
            min_val = query_comprimento - tolerancia
            max_val = query_comprimento + tolerancia

            is_within = min_val <= product_comprimento <= max_val

            details["validacoes"].append({
                "campo": "comprimento/largura",
                "query_valor": query_comprimento,
                "product_valor": product_comprimento,
                "min_aceito": min_val,
                "max_aceito": max_val,
                "resultado": "ok" if is_within else "fail"
            })

            if not is_within:
                return False, details

        # Validar altura (se especificada)
        if query_dimensions.altura and product.dimensoes.altura:
            tolerancia = query_dimensions.altura * self.tolerancia_dimensao
            min_val = query_dimensions.altura - tolerancia
            max_val = query_dimensions.altura + tolerancia

            is_within = min_val <= product.dimensoes.altura <= max_val

            details["validacoes"].append({
                "campo": "altura",
                "query_valor": query_dimensions.altura,
                "product_valor": product.dimensoes.altura,
                "min_aceito": min_val,
                "max_aceito": max_val,
                "resultado": "ok" if is_within else "fail"
            })

            if not is_within:
                return False, details

        return True, details

    def can_use_linear_meter(
        self,
        query_specs: Dict[str, Any],
        available_products: List[ProductSpecs]
    ) -> bool:
        """
        Verifica se pode usar cálculo de metro linear como fallback.

        Condições:
        1. Query tem dimensões especificadas
        2. Categoria suporta metro linear (mesa, bancada, sofá, etc.)
        3. Há produtos com dimensões válidas

        Args:
            query_specs: Especificações da query
            available_products: Lista de produtos encontrados

        Returns:
            True se metro linear é aplicável
        """
        # Verificar se tem dimensões na query
        query_dim = query_specs.get("dimensoes", {})
        if not query_dim:
            return False

        # Verificar categoria
        tipo_bem = str(query_specs.get("tipo_bem", "")).lower()
        categorias_linear = [
            "mesa", "bancada", "balcão", "balcao",
            "prateleira", "estante", "sofá", "sofa"
        ]

        if not any(cat in tipo_bem for cat in categorias_linear):
            return False

        # Verificar se há produtos com dimensões
        products_with_dims = [
            p for p in available_products
            if p.dimensoes and p.dimensoes.metro_linear
        ]

        return len(products_with_dims) >= 2
