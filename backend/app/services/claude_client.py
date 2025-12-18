import anthropic
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import base64
import json
import logging
import time
from app.services.prompts import (
    PROMPT_ANALISE_PATRIMONIAL,
    PROMPT_OCR_IMAGEM,
    PROMPT_PESQUISA_SPECS_WEB,
    PROMPT_GERADOR_QUERIES,
)

logger = logging.getLogger(__name__)


class ClaudeCallLog(BaseModel):
    """Log de uma chamada individual ao Claude"""
    activity: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    prompt: Optional[str] = None  # Prompt enviado para a IA


class FipeApiParams(BaseModel):
    """Parâmetros para consulta na API FIPE"""
    vehicle_type: Optional[str] = None  # cars | motorcycles | trucks
    codigo_fipe: Optional[str] = None
    busca_marca: Optional[Dict[str, Any]] = None
    busca_modelo: Optional[Dict[str, Any]] = None
    year_id_estimado: Optional[str] = None
    fluxo_recomendado: Optional[str] = None  # por_hierarquia | por_codigo_fipe
    endpoints: Optional[Dict[str, str]] = None


class ItemAnalysisResult(BaseModel):
    # Tipo de processamento: FIPE para veículos, GOOGLE_SHOPPING para demais
    tipo_processamento: str = "GOOGLE_SHOPPING"  # FIPE | GOOGLE_SHOPPING

    # Dados do bem
    nome_canonico: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    categoria: Optional[str] = None  # Veículos, Eletrônicos, Mobiliário, etc.
    natureza: Optional[str] = None  # veiculo_carro, veiculo_moto, veiculo_caminhao, eletronico, etc.

    # Campos legados (mantidos para compatibilidade)
    part_number: Optional[str] = None
    codigo_interno: Optional[str] = None
    especificacoes_tecnicas: Dict[str, Any] = {}  # Especificações técnicas extraídas
    palavras_chave: List[str] = []
    sinonimos: List[str] = []
    query_principal: str = ""  # Query baseada nas especificações técnicas
    query_alternativas: List[str] = []
    termos_excluir: List[str] = []
    observacoes: Optional[str] = None
    nivel_confianca: float = 0.0

    # Campos para API FIPE (veículos)
    fipe_api: Optional[FipeApiParams] = None
    fallback_google_shopping: Optional[Dict[str, Any]] = None
    dados_faltantes: List[str] = []
    especificacoes: Dict[str, Any] = {}  # Especificações no formato {essenciais: {}, complementares: {}}

    # Metadados
    total_tokens_used: int = 0  # Total de tokens usados em todas as chamadas
    call_logs: List[ClaudeCallLog] = []  # Log detalhado de cada chamada


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.total_tokens_used = 0  # Rastrear tokens usados
        self.call_logs: List[ClaudeCallLog] = []  # Log de todas as chamadas

    def _call_with_retry(self, func, max_retries=5):
        """Chama a API com retry exponencial em caso de rate limit ou API sobrecarregada"""
        for attempt in range(max_retries):
            try:
                return func()
            except anthropic.RateLimitError as e:
                if attempt == max_retries - 1:
                    raise

                # Extrair tempo de espera do erro, ou usar backoff exponencial
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                logger.warning(f"Rate limit atingido. Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            except anthropic.APIStatusError as e:
                # Tratar erro 529 (overloaded) com retry
                if e.status_code == 529:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s, 20s, 25s
                    logger.warning(f"API sobrecarregada (529). Aguardando {wait_time}s antes de tentar novamente (tentativa {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                raise

    async def analyze_item(
        self,
        input_text: Optional[str] = None,
        image_files: Optional[List[bytes]] = None
    ) -> ItemAnalysisResult:
        """
        Analisa item em duas etapas:
        1. Análise da descrição de texto OU OCR de imagem
        2. Se specs relevantes não estiverem visíveis, busca na web
        """
        # Se só tiver texto (sem imagem), usar fluxo simplificado
        if input_text and not image_files:
            return await self._analyze_text_only(input_text)

        content = []

        if input_text:
            content.append({
                "type": "text",
                "text": f"Descrição fornecida: {input_text}"
            })

        if image_files:
            for img_data in image_files:
                img_base64 = base64.standard_b64encode(img_data).decode("utf-8")
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64,
                    },
                })

        # ETAPA 1: OCR e identificação básica (prompt importado de prompts.py)
        content.insert(0, {"type": "text", "text": PROMPT_OCR_IMAGEM})

        logger.info("Etapa 1: OCR e identificação básica")
        ocr_response = self._call_with_retry(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": content}]
            )
        )

        # Registrar tokens usados
        if hasattr(ocr_response, 'usage'):
            input_tokens = ocr_response.usage.input_tokens
            output_tokens = ocr_response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            # Registrar log da chamada
            self.call_logs.append(ClaudeCallLog(
                activity="OCR e identificação básica da imagem",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=ocr_prompt
            ))

            logger.info(f"OCR tokens: {total_tokens}")

        ocr_text = ocr_response.content[0].text
        ocr_data = self._parse_json(ocr_text)

        # Extrair identificadores (novo formato com objeto identificadores)
        identificadores = ocr_data.get('identificadores', {})
        tipo_produto = identificadores.get('tipo_produto') or ocr_data.get('tipo_produto')
        marca = identificadores.get('marca') or ocr_data.get('marca')
        modelo = identificadores.get('modelo') or ocr_data.get('modelo')
        numero_serie = identificadores.get('numero_serie')
        part_number = identificadores.get('part_number')

        # Normalizar ocr_data para manter compatibilidade
        ocr_data['tipo_produto'] = tipo_produto
        ocr_data['marca'] = marca
        ocr_data['modelo'] = modelo
        ocr_data['numero_serie'] = numero_serie
        ocr_data['part_number'] = part_number

        logger.info(f"OCR resultado: tipo={tipo_produto}, marca={marca}, modelo={modelo}, S/N={numero_serie}")
        logger.info(f"Tem specs relevantes: {ocr_data.get('tem_specs_relevantes')}, Pode consultar fabricante: {ocr_data.get('pode_consultar_fabricante')}")

        # ETAPA 2: Busca web se necessário (specs não visíveis na imagem)
        specs_from_web = {}
        if not ocr_data.get('tem_specs_relevantes', False) and marca and modelo:
            tipo = tipo_produto or 'produto'

            logger.info(f"Etapa 2: Buscando specs na web para {marca} {modelo} (S/N: {numero_serie}, P/N: {part_number})")
            specs_from_web = await self._search_specs_on_web(marca, modelo, tipo, numero_serie, part_number)
            logger.info(f"Specs encontradas na web: {specs_from_web}")

        # ETAPA 3: Gerar resultado final com todas as informações
        final_prompt = self._build_final_prompt(ocr_data, specs_from_web)

        logger.info("Etapa 3: Gerando análise final")
        final_response = self._call_with_retry(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": final_prompt}]
            )
        )

        # Registrar tokens usados
        if hasattr(final_response, 'usage'):
            input_tokens = final_response.usage.input_tokens
            output_tokens = final_response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            # Registrar log da chamada
            self.call_logs.append(ClaudeCallLog(
                activity="Análise final e geração de query de busca",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=final_prompt
            ))

            logger.info(f"Final analysis tokens: {total_tokens}")

        response_text = final_response.content[0].text
        data = self._parse_json(response_text)

        # Adicionar total de tokens e logs ao resultado
        data['total_tokens_used'] = self.total_tokens_used
        data['call_logs'] = [log.dict() for log in self.call_logs]

        return ItemAnalysisResult(**data)

    async def _search_specs_on_web(self, marca: str, modelo: str, tipo: str, numero_serie: Optional[str] = None, part_number: Optional[str] = None) -> Dict[str, Any]:
        """Busca especificações técnicas na web usando web_search do Claude"""

        # Prompt importado de prompts.py com substituição de variáveis
        search_prompt = PROMPT_PESQUISA_SPECS_WEB.format(
            marca=marca,
            modelo=modelo,
            tipo=tipo,
            part_number=part_number or 'null',
            numero_serie=numero_serie or 'null'
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3
                }],
                messages=[{"role": "user", "content": search_prompt}]
            )

            # Registrar tokens usados
            if hasattr(response, 'usage'):
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                self.total_tokens_used += total_tokens

                # Registrar log da chamada
                self.call_logs.append(ClaudeCallLog(
                    activity=f"Busca de especificações técnicas na web: {marca} {modelo}",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    prompt=search_prompt
                ))

                logger.info(f"Web search tokens: {total_tokens}")

            # Processar resposta que pode conter tool_use e text
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text

            if result_text:
                return self._parse_json(result_text)
            return {}

        except Exception as e:
            logger.warning(f"Erro ao buscar specs na web: {e}")
            return {}

    def _build_final_prompt(self, ocr_data: Dict, web_specs: Dict) -> str:
        """Constrói o prompt final combinando OCR + specs da web"""

        specs_info = ""
        if web_specs:
            specs_info = f"""
## ESPECIFICAÇÕES ENCONTRADAS NA WEB:
{json.dumps(web_specs, indent=2, ensure_ascii=False)}

Use estas especificações para criar a query de busca.
"""

        # Prompt importado de prompts.py com substituição de variáveis
        return PROMPT_GERADOR_QUERIES.format(
            ocr_completo=ocr_data.get('ocr_completo', 'N/A'),
            tipo_produto=ocr_data.get('tipo_produto', 'N/A'),
            marca=ocr_data.get('marca', 'N/A'),
            modelo=ocr_data.get('modelo', 'N/A'),
            specs_visiveis=json.dumps(ocr_data.get('specs_visiveis') or {}, ensure_ascii=False),
            specs_info=specs_info
        )

    async def _analyze_text_only(self, input_text: str) -> ItemAnalysisResult:
        """Analisa apenas texto (sem imagem) de forma direta.
        Suporta veículos (retorna dados para API FIPE) e bens gerais (Google Shopping).
        """
        logger.info("Analisando texto puro (sem imagem)")

        # Usar o prompt do arquivo de templates
        prompt = PROMPT_ANALISE_PATRIMONIAL.replace("{input_text}", input_text)

        response = self._call_with_retry(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
        )

        # Registrar tokens
        if hasattr(response, 'usage'):
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            self.call_logs.append(ClaudeCallLog(
                activity="Análise de descrição de texto (reavaliação patrimonial)",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=prompt
            ))

            logger.info(f"Text analysis tokens: {total_tokens}")

        response_text = response.content[0].text
        raw_data = self._parse_json(response_text)

        # Transformar novo formato para formato compatível com ItemAnalysisResult
        data = self._transform_patrimonial_response(raw_data)

        # Adicionar total de tokens e logs
        data['total_tokens_used'] = self.total_tokens_used
        data['call_logs'] = [log.dict() for log in self.call_logs]

        return ItemAnalysisResult(**data)

    def _transform_patrimonial_response(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transforma resposta do formato patrimonial para formato ItemAnalysisResult.
        Suporta tanto veículos (FIPE) quanto bens gerais (Google Shopping).
        """
        tipo_processamento = raw_data.get('tipo_processamento', 'GOOGLE_SHOPPING')
        bem = raw_data.get('bem_patrimonial', {})
        specs = raw_data.get('especificacoes', {})
        avaliacao = raw_data.get('avaliacao', {})

        # Combinar especificações essenciais e complementares
        especificacoes_tecnicas = {}
        especificacoes_tecnicas.update(specs.get('essenciais', {}))
        especificacoes_tecnicas.update(specs.get('complementares', {}))

        # Base result
        result = {
            'tipo_processamento': tipo_processamento,
            'nome_canonico': bem.get('nome_canonico', ''),
            'marca': bem.get('marca'),
            'modelo': bem.get('modelo'),
            'categoria': bem.get('categoria'),
            'natureza': bem.get('natureza'),
            'part_number': None,
            'codigo_interno': None,
            'especificacoes_tecnicas': especificacoes_tecnicas,
            'especificacoes': specs,  # Manter formato original {essenciais: {}, complementares: {}}
            'observacoes': avaliacao.get('observacoes', ''),
            'nivel_confianca': avaliacao.get('confianca', 0.0),
            'dados_faltantes': avaliacao.get('dados_faltantes', []),
        }

        # Processar conforme tipo
        if tipo_processamento == 'FIPE':
            # Veículo - dados para API FIPE
            fipe_api_data = raw_data.get('fipe_api', {})
            classificacao_veiculo = raw_data.get('classificacao_veiculo', {})

            # Usar vehicle_type da classificacao_veiculo se disponível, senão usar de fipe_api
            vehicle_type = classificacao_veiculo.get('vehicle_type') or fipe_api_data.get('vehicle_type')

            result['fipe_api'] = FipeApiParams(
                vehicle_type=vehicle_type,
                codigo_fipe=fipe_api_data.get('codigo_fipe'),
                busca_marca=fipe_api_data.get('busca_marca'),
                busca_modelo=fipe_api_data.get('busca_modelo'),
                year_id_estimado=fipe_api_data.get('year_id_estimado'),
                fluxo_recomendado=fipe_api_data.get('fluxo_recomendado'),
                endpoints=fipe_api_data.get('endpoints')
            )
            result['fallback_google_shopping'] = raw_data.get('fallback_google_shopping', {})

            # Preservar informações de classificação de veículo para debug/auditoria
            if classificacao_veiculo:
                result['especificacoes_tecnicas']['classificacao_veiculo'] = classificacao_veiculo

            # Query principal vazia para veículos (usa FIPE)
            result['query_principal'] = ''
            result['query_alternativas'] = []
            result['palavras_chave'] = []
            result['termos_excluir'] = []
            result['sinonimos'] = []
        else:
            # Bem geral - dados para Google Shopping
            queries = raw_data.get('queries', {})
            busca = raw_data.get('busca', {})

            result['query_principal'] = queries.get('principal', '')
            result['query_alternativas'] = queries.get('alternativas', [])
            result['palavras_chave'] = busca.get('palavras_chave', [])
            result['termos_excluir'] = busca.get('termos_excluir', [])
            result['sinonimos'] = []
            result['fipe_api'] = None
            result['fallback_google_shopping'] = None

        return result

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extrai e parseia JSON de uma string"""
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = text[json_start:json_end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"Erro ao parsear JSON: {json_str[:200]}")
                return {}
        return {}
