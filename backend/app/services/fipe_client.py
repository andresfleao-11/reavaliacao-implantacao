"""
Cliente para API FIPE (Tabela FIPE de veículos)
Documentação: https://deividfortuna.github.io/fipe/v2/
"""
import httpx
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class FipeBrand(BaseModel):
    """Marca de veículo na FIPE"""
    code: str
    name: str


class FipeModel(BaseModel):
    """Modelo de veículo na FIPE"""
    code: str
    name: str


class FipeYear(BaseModel):
    """Ano disponível para um modelo na FIPE"""
    code: str  # formato: AAAA-C (ex: 2020-1)
    name: str  # descrição (ex: "2020 Gasolina")


class FipePrice(BaseModel):
    """Resultado da consulta de preço FIPE"""
    price: str  # Preço formatado (ex: "R$ 45.000,00")
    brand: str
    model: str
    modelYear: int
    fuel: str
    codeFipe: str
    referenceMonth: str
    vehicleType: int  # 1=carro, 2=moto, 3=caminhão
    fuelAcronym: str

    @property
    def price_value(self) -> float:
        """Extrai valor numérico do preço"""
        try:
            # Remove "R$ " e converte para float
            clean = self.price.replace("R$ ", "").replace(".", "").replace(",", ".")
            return float(clean)
        except:
            return 0.0


class FipeSearchResult(BaseModel):
    """Resultado completo de uma busca FIPE"""
    success: bool
    price: Optional[FipePrice] = None
    brand_id: Optional[str] = None
    brand_name: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    year_id: Optional[str] = None
    error_message: Optional[str] = None
    api_calls: int = 0
    search_path: List[str] = []  # Registro do caminho de busca


class FipeClient:
    """Cliente para a API FIPE"""

    BASE_URL = "https://fipe.parallelum.com.br/api/v2"

    # Mapeamento de tipos de veículo
    VEHICLE_TYPES = {
        "cars": "carros",
        "motorcycles": "motos",
        "trucks": "caminhões"
    }

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.api_calls = 0
        self.search_path = []

    def _similarity(self, a: str, b: str) -> float:
        """Calcula similaridade entre duas strings"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _normalize_brand(self, brand: str) -> str:
        """Normaliza nome de marca para busca"""
        mappings = {
            "vw": "volkswagen",
            "volks": "volkswagen",
            "gm": "chevrolet",
            "mb": "mercedes-benz",
            "mercedes": "mercedes-benz",
        }
        brand_lower = brand.lower().strip()
        return mappings.get(brand_lower, brand_lower)

    async def get_brands(self, vehicle_type: str) -> List[FipeBrand]:
        """Lista todas as marcas para um tipo de veículo"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/brands"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [FipeBrand(code=item["code"], name=item["name"]) for item in data]

    async def get_models(self, vehicle_type: str, brand_id: str) -> List[FipeModel]:
        """Lista modelos de uma marca"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/brands/{brand_id}/models"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [FipeModel(code=item["code"], name=item["name"]) for item in data]

    async def get_years_by_brand(self, vehicle_type: str, brand_id: str) -> List[FipeYear]:
        """Lista anos disponíveis para uma marca (NOVO FLUXO)"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/brands/{brand_id}/years"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [FipeYear(code=item["code"], name=item["name"]) for item in data]

    async def get_models_by_brand_year(
        self,
        vehicle_type: str,
        brand_id: str,
        year_id: str
    ) -> List[FipeModel]:
        """Lista modelos disponíveis para uma marca e ano específico (NOVO FLUXO)"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/brands/{brand_id}/years/{year_id}/models"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [FipeModel(code=item["code"], name=item["name"]) for item in data]

    async def get_years(self, vehicle_type: str, brand_id: str, model_id: str) -> List[FipeYear]:
        """Lista anos disponíveis para um modelo"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/brands/{brand_id}/models/{model_id}/years"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [FipeYear(code=item["code"], name=item["name"]) for item in data]

    async def get_years_by_fipe_code(self, vehicle_type: str, fipe_code: str) -> List[FipeYear]:
        """Lista anos disponíveis por código FIPE"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/{fipe_code}/years"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [FipeYear(code=item["code"], name=item["name"]) for item in data]

    async def get_price(
        self,
        vehicle_type: str,
        brand_id: str,
        model_id: str,
        year_id: str
    ) -> FipePrice:
        """Obtém preço FIPE para um veículo específico"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/brands/{brand_id}/models/{model_id}/years/{year_id}"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return FipePrice(**data)

    async def get_price_by_fipe_code(
        self,
        vehicle_type: str,
        fipe_code: str,
        year_id: str
    ) -> FipePrice:
        """Obtém preço FIPE por código FIPE"""
        self.api_calls += 1
        url = f"{self.BASE_URL}/{vehicle_type}/{fipe_code}/years/{year_id}"
        self.search_path.append(f"GET {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return FipePrice(**data)

    async def find_brand(
        self,
        vehicle_type: str,
        search_term: str,
        variations: List[str] = None
    ) -> Optional[FipeBrand]:
        """Busca marca por nome (com variações)"""
        brands = await self.get_brands(vehicle_type)

        # Normalizar termo de busca
        normalized_search = self._normalize_brand(search_term)

        # Lista de termos para buscar (principal + variações)
        search_terms = [normalized_search]
        if variations:
            search_terms.extend([self._normalize_brand(v) for v in variations])

        best_match = None
        best_score = 0.0

        for brand in brands:
            brand_name_lower = brand.name.lower()

            for term in search_terms:
                # Busca exata (ignorando case)
                if term in brand_name_lower or brand_name_lower in term:
                    logger.info(f"Marca encontrada (match direto): {brand.name}")
                    return brand

                # Busca por similaridade
                score = self._similarity(term, brand_name_lower)
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = brand

        if best_match:
            logger.info(f"Marca encontrada (similaridade {best_score:.2f}): {best_match.name}")
        else:
            logger.warning(f"Marca não encontrada: {search_term}")

        return best_match

    async def find_model(
        self,
        vehicle_type: str,
        brand_id: str,
        search_term: str,
        variations: List[str] = None,
        keywords: List[str] = None
    ) -> Optional[FipeModel]:
        """Busca modelo por nome (com variações e palavras-chave)"""
        models = await self.get_models(vehicle_type, brand_id)

        search_terms = [search_term.lower()]
        if variations:
            search_terms.extend([v.lower() for v in variations])

        best_match = None
        best_score = 0.0

        for model in models:
            model_name_lower = model.name.lower()

            # Busca por palavras-chave (todas devem estar presentes)
            if keywords:
                all_keywords_match = all(
                    kw.lower() in model_name_lower
                    for kw in keywords
                )
                if all_keywords_match:
                    logger.info(f"Modelo encontrado (keywords): {model.name}")
                    return model

            for term in search_terms:
                # Match exato ou parcial
                if term in model_name_lower or model_name_lower in term:
                    logger.info(f"Modelo encontrado (match direto): {model.name}")
                    return model

                # Similaridade
                score = self._similarity(term, model_name_lower)
                if score > best_score and score > 0.5:
                    best_score = score
                    best_match = model

        if best_match:
            logger.info(f"Modelo encontrado (similaridade {best_score:.2f}): {best_match.name}")
        else:
            logger.warning(f"Modelo não encontrado: {search_term}")

        return best_match

    async def find_year(
        self,
        years: List[FipeYear],
        year_id_estimado: str = None,
        ano_modelo: str = None
    ) -> Optional[FipeYear]:
        """Encontra o ano mais adequado na lista"""
        if not years:
            return None

        # Se tiver year_id_estimado exato, tentar encontrar
        if year_id_estimado:
            for year in years:
                if year.code == year_id_estimado:
                    return year

        # Se tiver ano_modelo, buscar pelo ano
        if ano_modelo:
            for year in years:
                if ano_modelo in year.code or ano_modelo in year.name:
                    return year

        # Retornar o mais recente (primeiro da lista geralmente)
        return years[0] if years else None

    async def search_vehicle(
        self,
        vehicle_type: str,
        busca_marca: Dict[str, Any],
        busca_modelo: Dict[str, Any],
        year_id_estimado: str = None,
        codigo_fipe: str = None,
        ano_modelo: str = None
    ) -> FipeSearchResult:
        """
        Busca completa de veículo na FIPE.

        Args:
            vehicle_type: cars, motorcycles ou trucks
            busca_marca: {"termo_principal": str, "variacoes": List[str]}
            busca_modelo: {"termo_principal": str, "variacoes": List[str], "palavras_chave": List[str]}
            year_id_estimado: Ex: "2020-1"
            codigo_fipe: Código FIPE se disponível
            ano_modelo: Ano do modelo (ex: "2020")

        Returns:
            FipeSearchResult com resultado da busca
        """
        self.api_calls = 0
        self.search_path = []

        try:
            # Se tiver código FIPE, usar fluxo direto
            if codigo_fipe:
                logger.info(f"Buscando por código FIPE: {codigo_fipe}")
                years = await self.get_years_by_fipe_code(vehicle_type, codigo_fipe)

                year = await self.find_year(years, year_id_estimado, ano_modelo)
                if not year:
                    return FipeSearchResult(
                        success=False,
                        error_message="Ano não encontrado para o código FIPE",
                        api_calls=self.api_calls,
                        search_path=self.search_path
                    )

                price = await self.get_price_by_fipe_code(vehicle_type, codigo_fipe, year.code)

                return FipeSearchResult(
                    success=True,
                    price=price,
                    year_id=year.code,
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            # Fluxo por hierarquia (marca -> modelo -> ano)
            logger.info(f"Buscando marca: {busca_marca.get('termo_principal')}")
            brand = await self.find_brand(
                vehicle_type,
                busca_marca.get('termo_principal', ''),
                busca_marca.get('variacoes', [])
            )

            if not brand:
                return FipeSearchResult(
                    success=False,
                    error_message=f"Marca não encontrada: {busca_marca.get('termo_principal')}",
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            logger.info(f"Buscando modelo: {busca_modelo.get('termo_principal')}")
            model = await self.find_model(
                vehicle_type,
                brand.code,
                busca_modelo.get('termo_principal', ''),
                busca_modelo.get('variacoes', []),
                busca_modelo.get('palavras_chave', [])
            )

            if not model:
                return FipeSearchResult(
                    success=False,
                    error_message=f"Modelo não encontrado: {busca_modelo.get('termo_principal')}",
                    brand_id=brand.code,
                    brand_name=brand.name,
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            logger.info(f"Buscando anos para {brand.name} {model.name}")
            years = await self.get_years(vehicle_type, brand.code, model.code)

            year = await self.find_year(years, year_id_estimado, ano_modelo)
            if not year:
                return FipeSearchResult(
                    success=False,
                    error_message="Ano não encontrado para o modelo",
                    brand_id=brand.code,
                    brand_name=brand.name,
                    model_id=model.code,
                    model_name=model.name,
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            logger.info(f"Obtendo preço FIPE para {year.name}")
            price = await self.get_price(vehicle_type, brand.code, model.code, year.code)

            return FipeSearchResult(
                success=True,
                price=price,
                brand_id=brand.code,
                brand_name=brand.name,
                model_id=model.code,
                model_name=model.name,
                year_id=year.code,
                api_calls=self.api_calls,
                search_path=self.search_path
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP na API FIPE: {e}")
            return FipeSearchResult(
                success=False,
                error_message=f"Erro na API FIPE: {e.response.status_code}",
                api_calls=self.api_calls,
                search_path=self.search_path
            )
        except Exception as e:
            logger.error(f"Erro ao buscar na FIPE: {e}")
            return FipeSearchResult(
                success=False,
                error_message=str(e),
                api_calls=self.api_calls,
                search_path=self.search_path
            )

    async def search_vehicle_optimized(
        self,
        vehicle_type: str,
        busca_marca: Dict[str, Any],
        busca_modelo: Dict[str, Any],
        year_id_estimado: str = None,
        ano_modelo: str = None,
        combustivel: str = None
    ) -> FipeSearchResult:
        """
        Busca de veículo com fluxo OTIMIZADO:

        1. GET /brands → lista marcas
        2. Seleciona marca (fuzzy match)
        3. GET /brands/{brand_id}/years → lista anos por marca
        4. Seleciona ano baseado no ano_modelo + combustivel (texto) retornado pela IA
        5. GET /brands/{brand_id}/years/{year_id}/models → lista modelos por marca e ano
        6. Seleciona modelo (fuzzy match - menos opções, mais preciso)
        7. GET /brands/{brand_id}/models/{model_id}/years/{year_id} → preço

        Args:
            vehicle_type: cars, motorcycles ou trucks
            busca_marca: {"termo_principal": str, "variacoes": List[str]}
            busca_modelo: {"termo_principal": str, "variacoes": List[str], "palavras_chave": List[str]}
            year_id_estimado: Ex: "2020-1" (opcional, se IA souber o código exato)
            ano_modelo: Ano do modelo (ex: "2020")
            combustivel: Texto do combustível retornado pela IA (ex: "flex", "gasolina", "diesel")

        Returns:
            FipeSearchResult com resultado da busca
        """
        self.api_calls = 0
        self.search_path = []

        try:
            # PASSO 1: Buscar marcas
            logger.info(f"[FIPE-OPT] Passo 1: Buscando marcas...")
            brand = await self.find_brand(
                vehicle_type,
                busca_marca.get('termo_principal', ''),
                busca_marca.get('variacoes', [])
            )

            if not brand:
                return FipeSearchResult(
                    success=False,
                    error_message=f"Marca não encontrada: {busca_marca.get('termo_principal')}",
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            logger.info(f"[FIPE-OPT] Passo 2: Marca selecionada: {brand.name} (ID: {brand.code})")

            # PASSO 3: Buscar anos disponíveis para a marca
            logger.info(f"[FIPE-OPT] Passo 3: Buscando anos para marca {brand.name}...")
            years = await self.get_years_by_brand(vehicle_type, brand.code)

            if not years:
                return FipeSearchResult(
                    success=False,
                    error_message=f"Nenhum ano disponível para a marca {brand.name}",
                    brand_id=brand.code,
                    brand_name=brand.name,
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            # PASSO 4: Selecionar ano baseado no ano_modelo + combustivel (texto da IA)
            # A seleção é feita pelo NOME do ano retornado pela API, não pelo código predefinido
            # IMPORTANTE: Sempre buscar pelo texto do combustível, ignorando year_id_estimado da IA
            # pois pode estar incorreto (ex: IA mapeia Flex para código 1 quando deveria ser 5)
            selected_year = None

            # Buscar por ano_modelo + combustivel (texto da IA)
            if ano_modelo:
                # Normalizar o combustível da IA para busca
                combustivel_normalizado = (combustivel or "").lower().strip()

                # Mapeamento de variações de combustível para termos de busca
                combustivel_termos = {
                    "flex": ["flex"],
                    "gasolina": ["gasolina"],
                    "diesel": ["diesel"],
                    "alcool": ["álcool", "alcool"],
                    "etanol": ["álcool", "alcool"],
                    "hibrido": ["híbrido", "hibrido"],
                    "híbrido": ["híbrido", "hibrido"],
                    "eletrico": ["elétrico", "eletrico"],
                    "elétrico": ["elétrico", "eletrico"],
                    "gnv": ["gnv", "gás"],
                }

                # Determinar termos de busca para o combustível
                termos_busca = []
                for key, termos in combustivel_termos.items():
                    if key in combustivel_normalizado:
                        termos_busca = termos
                        break

                if not termos_busca and combustivel_normalizado:
                    termos_busca = [combustivel_normalizado]

                logger.info(f"[FIPE-OPT] Buscando ano {ano_modelo} com combustível '{combustivel}' (termos: {termos_busca})")

                # Buscar ano que contenha o ano_modelo E o combustível no nome
                for year in years:
                    year_name_lower = year.name.lower()

                    # Verificar se o ano modelo está no nome
                    if ano_modelo not in year.code and ano_modelo not in year_name_lower:
                        continue

                    # Se temos termos de combustível, verificar se algum está no nome
                    if termos_busca:
                        for termo in termos_busca:
                            if termo in year_name_lower:
                                selected_year = year
                                logger.info(f"[FIPE-OPT] Ano encontrado por texto: {year.name} (código: {year.code})")
                                break

                    if selected_year:
                        break

                # Se não encontrou com combustível específico, buscar apenas pelo ano
                if not selected_year:
                    logger.warning(f"[FIPE-OPT] Combustível '{combustivel}' não encontrado para ano {ano_modelo}")
                    for year in years:
                        if year.code.startswith(ano_modelo) or ano_modelo in year.name:
                            selected_year = year
                            logger.info(f"[FIPE-OPT] Usando primeiro ano disponível para {ano_modelo}: {year.name}")
                            break

            # Fallback: primeiro ano disponível
            if not selected_year:
                selected_year = years[0]
                logger.warning(f"[FIPE-OPT] Ano {ano_modelo} não encontrado, usando mais recente: {selected_year.name}")

            logger.info(f"[FIPE-OPT] Passo 4: Ano selecionado: {selected_year.name} (ID: {selected_year.code})")

            # PASSO 5: Buscar modelos para marca e ano
            logger.info(f"[FIPE-OPT] Passo 5: Buscando modelos para {brand.name} / {selected_year.name}...")
            models = await self.get_models_by_brand_year(vehicle_type, brand.code, selected_year.code)

            if not models:
                return FipeSearchResult(
                    success=False,
                    error_message=f"Nenhum modelo disponível para {brand.name} ano {selected_year.name}",
                    brand_id=brand.code,
                    brand_name=brand.name,
                    year_id=selected_year.code,
                    api_calls=self.api_calls,
                    search_path=self.search_path
                )

            # PASSO 6: Selecionar modelo (fuzzy match)
            logger.info(f"[FIPE-OPT] Passo 6: Selecionando modelo entre {len(models)} opções...")
            selected_model = await self._find_model_in_list(
                models,
                busca_modelo.get('termo_principal', ''),
                busca_modelo.get('variacoes', []),
                busca_modelo.get('palavras_chave', [])
            )

            if not selected_model:
                # FALLBACK: Tentar fluxo tradicional (marca → modelos → ano)
                logger.warning(f"[FIPE-OPT] Modelo '{busca_modelo.get('termo_principal')}' não encontrado para ano {selected_year.name}")
                logger.info(f"[FIPE-OPT] Tentando FALLBACK com fluxo tradicional...")

                # Buscar TODOS os modelos da marca (sem filtro de ano)
                all_models = await self.get_models(vehicle_type, brand.code)

                # Tentar encontrar o modelo na lista completa
                selected_model = await self._find_model_in_list(
                    all_models,
                    busca_modelo.get('termo_principal', ''),
                    busca_modelo.get('variacoes', []),
                    busca_modelo.get('palavras_chave', [])
                )

                if not selected_model:
                    # Realmente não existe o modelo
                    available = ", ".join([m.name for m in models[:5]])
                    return FipeSearchResult(
                        success=False,
                        error_message=f"Modelo não encontrado: {busca_modelo.get('termo_principal')}. Disponíveis: {available}...",
                        brand_id=brand.code,
                        brand_name=brand.name,
                        year_id=selected_year.code,
                        api_calls=self.api_calls,
                        search_path=self.search_path
                    )

                logger.info(f"[FIPE-OPT] FALLBACK: Modelo encontrado: {selected_model.name}")

                # Buscar anos disponíveis para este modelo específico
                model_years = await self.get_years(vehicle_type, brand.code, selected_model.code)

                if not model_years:
                    return FipeSearchResult(
                        success=False,
                        error_message=f"Nenhum ano disponível para o modelo {selected_model.name}",
                        brand_id=brand.code,
                        brand_name=brand.name,
                        model_id=selected_model.code,
                        model_name=selected_model.name,
                        api_calls=self.api_calls,
                        search_path=self.search_path
                    )

                # Selecionar ano mais adequado para este modelo
                fallback_year = await self.find_year(model_years, year_id_estimado, ano_modelo)
                if not fallback_year:
                    fallback_year = model_years[0]  # Usar o mais recente

                logger.info(f"[FIPE-OPT] FALLBACK: Ano selecionado: {fallback_year.name}")

                # Usar este ano no lugar do selecionado anteriormente
                selected_year = fallback_year

            logger.info(f"[FIPE-OPT] Passo 6: Modelo selecionado: {selected_model.name} (ID: {selected_model.code})")

            # PASSO 7: Obter preço FIPE
            logger.info(f"[FIPE-OPT] Passo 7: Obtendo preço FIPE...")
            price = await self.get_price(vehicle_type, brand.code, selected_model.code, selected_year.code)

            logger.info(f"[FIPE-OPT] SUCESSO: {price.brand} {price.model} {price.modelYear} = {price.price}")

            return FipeSearchResult(
                success=True,
                price=price,
                brand_id=brand.code,
                brand_name=brand.name,
                model_id=selected_model.code,
                model_name=selected_model.name,
                year_id=selected_year.code,
                api_calls=self.api_calls,
                search_path=self.search_path
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"[FIPE-OPT] Erro HTTP: {e}")
            return FipeSearchResult(
                success=False,
                error_message=f"Erro na API FIPE: {e.response.status_code}",
                api_calls=self.api_calls,
                search_path=self.search_path
            )
        except Exception as e:
            logger.error(f"[FIPE-OPT] Erro: {e}")
            return FipeSearchResult(
                success=False,
                error_message=str(e),
                api_calls=self.api_calls,
                search_path=self.search_path
            )

    async def _find_model_in_list(
        self,
        models: List[FipeModel],
        search_term: str,
        variations: List[str] = None,
        keywords: List[str] = None
    ) -> Optional[FipeModel]:
        """
        Busca modelo em uma lista já filtrada (sem chamada API).

        Estratégia de matching (em ordem de prioridade):
        1. Match exato de keywords (todas presentes)
        2. Match por palavras do termo principal (quanto mais palavras, melhor)
        3. Match por similaridade de string
        """
        search_terms = [search_term.lower()]
        if variations:
            search_terms.extend([v.lower() for v in variations])

        best_match = None
        best_score = 0.0
        best_word_count = 0

        # Extrair palavras significativas do termo de busca (ignorar palavras muito curtas)
        search_words = [w for w in search_term.lower().split() if len(w) >= 2]
        logger.info(f"[FIPE-OPT] Buscando modelo com palavras: {search_words}")

        for model in models:
            model_name_lower = model.name.lower()

            # 1. Busca por keywords (todas devem estar presentes)
            if keywords:
                all_keywords_match = all(
                    kw.lower() in model_name_lower
                    for kw in keywords
                )
                if all_keywords_match:
                    logger.info(f"[FIPE-OPT] Modelo por keywords: {model.name}")
                    return model

            # 2. Contar quantas palavras do termo de busca estão no modelo
            matching_words = sum(1 for word in search_words if word in model_name_lower)

            # Se encontrou modelo com mais palavras coincidentes, priorizar
            if matching_words > best_word_count:
                best_word_count = matching_words
                best_match = model
                best_score = matching_words / len(search_words) if search_words else 0
                logger.info(f"[FIPE-OPT] Candidato com {matching_words}/{len(search_words)} palavras: {model.name}")

            # 3. Se empate em palavras, usar similaridade como desempate
            elif matching_words == best_word_count and matching_words > 0:
                for term in search_terms:
                    score = self._similarity(term, model_name_lower)
                    if score > best_score:
                        best_score = score
                        best_match = model

            # 4. Fallback: Match direto simples (termo está no nome ou vice-versa)
            elif best_word_count == 0:
                for term in search_terms:
                    if term in model_name_lower or model_name_lower in term:
                        logger.info(f"[FIPE-OPT] Modelo por match direto: {model.name}")
                        return model

                    # Similaridade
                    score = self._similarity(term, model_name_lower)
                    if score > best_score and score > 0.5:
                        best_score = score
                        best_match = model

        if best_match:
            if best_word_count > 0:
                logger.info(f"[FIPE-OPT] Modelo por palavras ({best_word_count}/{len(search_words)}): {best_match.name}")
            else:
                logger.info(f"[FIPE-OPT] Modelo por similaridade ({best_score:.2f}): {best_match.name}")

        return best_match

    async def refresh_price(
        self,
        vehicle_type: str,
        brand_id: str,
        model_id: str,
        year_id: str
    ) -> FipeSearchResult:
        """
        Atualiza preço de um veículo já conhecido (para botão Atualizar).

        Args:
            vehicle_type: cars, motorcycles ou trucks
            brand_id: ID da marca
            model_id: ID do modelo
            year_id: ID do ano (ex: "2020-1")

        Returns:
            FipeSearchResult com novo preço
        """
        self.api_calls = 0
        self.search_path = []

        try:
            price = await self.get_price(vehicle_type, brand_id, model_id, year_id)

            return FipeSearchResult(
                success=True,
                price=price,
                brand_id=brand_id,
                model_id=model_id,
                year_id=year_id,
                api_calls=self.api_calls,
                search_path=self.search_path
            )

        except httpx.HTTPStatusError as e:
            return FipeSearchResult(
                success=False,
                error_message=f"Erro na API FIPE: {e.response.status_code}",
                api_calls=self.api_calls,
                search_path=self.search_path
            )
        except Exception as e:
            return FipeSearchResult(
                success=False,
                error_message=str(e),
                api_calls=self.api_calls,
                search_path=self.search_path
            )
