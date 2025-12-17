from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import json
import os


class QuoteCreateRequest(BaseModel):
    inputText: Optional[str] = None
    codigo: Optional[str] = None
    local: Optional[str] = None
    pesquisador: Optional[str] = None


class QuoteCreateResponse(BaseModel):
    quoteRequestId: int


class QuoteSourceResponse(BaseModel):
    id: int
    url: str
    domain: Optional[str]
    page_title: Optional[str]
    price_value: Optional[Decimal]
    currency: str
    extraction_method: Optional[str]
    captured_at: datetime
    is_outlier: bool
    is_accepted: bool
    screenshot_url: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class ProjectInfoResponse(BaseModel):
    """Informações resumidas do projeto para cotações"""
    id: int
    nome: str
    cliente_nome: Optional[str] = None
    config_versao: Optional[int] = None


class QuoteAttemptInfo(BaseModel):
    """Informação resumida de uma tentativa de cotação"""
    id: int
    attempt_number: int
    status: str
    created_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class QuoteDetailResponse(BaseModel):
    id: int
    status: str
    input_type: Optional[str] = None  # TEXT, IMAGE, GOOGLE_LENS
    created_at: datetime
    input_text: Optional[str]
    codigo_item: Optional[str]
    claude_payload_json: Optional[Dict[str, Any]]
    search_query_final: Optional[str]
    local: Optional[str]
    pesquisador: Optional[str]
    valor_medio: Optional[Decimal]
    valor_minimo: Optional[Decimal]
    valor_maximo: Optional[Decimal]
    variacao_percentual: Optional[Decimal] = None  # Variação = (MAX/MIN - 1) * 100
    error_message: Optional[str]
    sources: List[QuoteSourceResponse] = []
    pdf_url: Optional[str] = None
    # Informações do projeto
    project_id: Optional[int] = None
    project: Optional[ProjectInfoResponse] = None
    # Campos de progresso
    current_step: Optional[str] = None
    progress_percentage: Optional[int] = None
    step_details: Optional[str] = None
    # Parâmetros utilizados na cotação
    numero_cotacoes_configurado: Optional[int] = None
    variacao_maxima_percent: Optional[float] = None
    # Campos de tentativas
    attempt_number: int = 1
    original_quote_id: Optional[int] = None
    attempt_history: List[QuoteAttemptInfo] = []  # Histórico de todas as tentativas
    # ID da cotação filha (se já foi recotado)
    child_quote_id: Optional[int] = None
    # Lote (se pertence a um lote)
    batch_job_id: Optional[int] = None
    # JSON do Google Shopping (para debug e consulta)
    google_shopping_response_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class QuoteListItem(BaseModel):
    id: int
    status: str
    input_type: Optional[str] = None  # TEXT, IMAGE, GOOGLE_LENS
    created_at: datetime
    codigo_item: Optional[str]
    nome_item: Optional[str]
    valor_medio: Optional[Decimal]
    # Informações do projeto
    project_id: Optional[int] = None
    project_nome: Optional[str] = None
    cliente_nome: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class QuoteListResponse(BaseModel):
    items: List[QuoteListItem]
    total: int
    page: int
    per_page: int


class ParametersResponse(BaseModel):
    numero_cotacoes_por_pesquisa: int
    variacao_maxima_percent: float
    pesquisador_padrao: str
    local_padrao: str
    serpapi_location: str  # SerpAPI location for search (e.g., "Brazil", "Sao Paulo,State of Sao Paulo,Brazil")
    vigencia_cotacao_veiculos: int = 6  # Vigencia em meses para cotacoes de veiculos
    enable_price_mismatch_validation: bool = True  # Habilita/desabilita validação de PRICE_MISMATCH


class ParametersUpdateRequest(BaseModel):
    numero_cotacoes_por_pesquisa: Optional[int] = None
    variacao_maxima_percent: Optional[float] = None
    pesquisador_padrao: Optional[str] = None
    local_padrao: Optional[str] = None
    serpapi_location: Optional[str] = None
    vigencia_cotacao_veiculos: Optional[int] = None  # Vigencia em meses para cotacoes de veiculos
    enable_price_mismatch_validation: Optional[bool] = None  # Habilita/desabilita validação de PRICE_MISMATCH


# Mapeamento de estados brasileiros para siglas
STATE_ABBREVIATIONS = {
    "State of Acre": "AC",
    "State of Alagoas": "AL",
    "State of Amapa": "AP",
    "State of Amazonas": "AM",
    "State of Bahia": "BA",
    "State of Ceara": "CE",
    "Federal District": "DF",
    "State of Espirito Santo": "ES",
    "State of Goias": "GO",
    "State of Maranhao": "MA",
    "State of Mato Grosso": "MT",
    "State of Mato Grosso do Sul": "MS",
    "State of Minas Gerais": "MG",
    "State of Para": "PA",
    "State of Paraiba": "PB",
    "State of Parana": "PR",
    "State of Pernambuco": "PE",
    "State of Piaui": "PI",
    "State of Rio de Janeiro": "RJ",
    "State of Rio Grande do Norte": "RN",
    "State of Rio Grande do Sul": "RS",
    "State of Rondonia": "RO",
    "State of Roraima": "RR",
    "State of Santa Catarina": "SC",
    "State of Sao Paulo": "SP",
    "State of Sergipe": "SE",
    "State of Tocantins": "TO",
}


def _extract_state_abbrev(canonical_name: str) -> str:
    """Extrai a sigla do estado do canonical_name"""
    for state_name, abbrev in STATE_ABBREVIATIONS.items():
        if state_name in canonical_name:
            return abbrev
    return ""


# Load SerpAPI Brazil locations from JSON file
def _load_serpapi_locations():
    """Load SerpAPI locations from locationsbr.json file"""
    # Caminho para locationsbr.json na pasta data (montada em /data no container)
    locations_file = '/data/locationsbr.json'
    # Fallback para caminho local de desenvolvimento
    if not os.path.exists(locations_file):
        locations_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'locationsbr.json')

    try:
        with open(locations_file, 'r', encoding='utf-8') as f:
            raw_locations = json.load(f)

        # Transformar para o formato esperado {value, label}
        locations = []

        # Adicionar opção "Brasil inteiro" primeiro
        locations.append({"value": "Brazil", "label": "Brasil (País inteiro)"})

        # Tipos de localização permitidos
        ALLOWED_TYPES = {"City", "State"}

        # Processar localizações do arquivo
        for loc in raw_locations:
            canonical_name = loc.get("canonical_name", "")
            name = loc.get("name", "")
            target_type = loc.get("target_type", "")
            reach = loc.get("reach", 0)

            # Filtrar apenas cidades e estados
            if target_type not in ALLOWED_TYPES:
                continue

            # Pular localizações com alcance muito pequeno (menos de 50000 para cidades)
            if target_type == "City" and reach < 50000:
                continue

            state_abbrev = _extract_state_abbrev(canonical_name)

            if target_type == "City":
                if state_abbrev:
                    label = f"{name}, {state_abbrev}"
                else:
                    # Se não encontrou sigla, pular esta cidade
                    continue
            elif target_type == "State":
                # Extrair nome do estado sem "State of"
                state_name = name.replace("State of ", "")
                label = f"{state_name} (Estado)"
            else:
                label = name

            locations.append({
                "value": canonical_name,
                "label": label
            })

        # Remover duplicatas (pelo label para evitar entradas iguais visualmente)
        seen_labels = set()
        unique_locations = [locations[0]]  # Manter Brasil primeiro
        for loc in locations[1:]:
            if loc["label"] not in seen_labels:
                seen_labels.add(loc["label"])
                unique_locations.append(loc)

        # Ordenar por label (mantendo Brasil primeiro)
        brasil = unique_locations[0]
        rest = sorted(unique_locations[1:], key=lambda x: x["label"])

        return [brasil] + rest

    except Exception as e:
        print(f"Erro ao carregar locationsbr.json: {e}")
        # Fallback to basic locations if file not found
        return [
            {"value": "Brazil", "label": "Brasil (País inteiro)"},
            {"value": "Sao Paulo,State of Sao Paulo,Brazil", "label": "São Paulo, SP"},
            {"value": "Rio de Janeiro,State of Rio de Janeiro,Brazil", "label": "Rio de Janeiro, RJ"},
        ]

SERPAPI_BRAZIL_LOCATIONS = _load_serpapi_locations()


class SerpApiLocationOption(BaseModel):
    value: str
    label: str


class BankPriceResponse(BaseModel):
    id: int
    codigo: str
    material: str
    caracteristicas: Optional[str]
    vl_mercado: Optional[Decimal]
    update_mode: str
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class BankPriceCreateRequest(BaseModel):
    codigo: str
    material: str
    caracteristicas: Optional[str] = None
    vl_mercado: Optional[Decimal] = None
    update_mode: str = "MARKET"


class BankPriceUpdateRequest(BaseModel):
    material: Optional[str] = None
    caracteristicas: Optional[str] = None
    vl_mercado: Optional[Decimal] = None
    update_mode: Optional[str] = None


class RevaluationParamsResponse(BaseModel):
    ec_map: Dict[str, float]
    pu_map: Dict[str, float]
    vuf_map: Dict[str, float]
    weights: Dict[str, float]


class RevaluationParamsUpdateRequest(BaseModel):
    ec_map: Optional[Dict[str, float]] = None
    pu_map: Optional[Dict[str, float]] = None
    vuf_map: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None


class IntegrationSettingResponse(BaseModel):
    provider: str
    api_key_masked: str
    other_settings: Dict[str, Any]
    is_configured: bool = False
    source: Optional[str] = None  # "database" or "environment" or None


class IntegrationSettingUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    other_settings: Optional[Dict[str, Any]] = None


class IntegrationTestResponse(BaseModel):
    success: bool
    message: str


# Available Anthropic Claude models
ANTHROPIC_MODELS = [
    {"value": "claude-opus-4-5-20251101", "label": "Claude Opus 4.5 (Mais inteligente, melhor OCR)"},
    {"value": "claude-sonnet-4-5-20250929", "label": "Claude Sonnet 4.5 (Equilibrado)"},
    {"value": "claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku (Rapido e economico)"},
]

OPENAI_MODELS = [
    # GPT-5 Series - Modelos mais recentes (Responses API)
    {"value": "gpt-5.2", "label": "GPT-5.2 (Mais recente, recomendado)"},
    {"value": "gpt-5.2-pro", "label": "GPT-5.2 Pro (Maior capacidade)"},
    {"value": "gpt-5.1", "label": "GPT-5.1 (Coding avancado)"},
    {"value": "gpt-5.1-codex", "label": "GPT-5.1 Codex (Especializado em codigo)"},
    {"value": "gpt-5", "label": "GPT-5 (Base)"},
    {"value": "gpt-5-mini", "label": "GPT-5 Mini (Rapido e economico)"},
    {"value": "gpt-5-nano", "label": "GPT-5 Nano (Ultra-rapido)"},
    # O-Series - Modelos de Reasoning
    {"value": "o3", "label": "o3 (Reasoning avancado, STEM)"},
    {"value": "o4-mini", "label": "o4-mini (Reasoning rapido e economico)"},
    {"value": "o3-mini", "label": "o3-mini (Reasoning compacto)"},
    {"value": "o1", "label": "o1 (Reasoning, tarefas complexas)"},
    {"value": "o1-mini", "label": "o1-mini (Reasoning economico)"},
    # GPT-4o - Modelos multimodais (Vision + Texto + Audio)
    {"value": "gpt-4o", "label": "GPT-4o (Multimodal, Vision + Audio)"},
    {"value": "gpt-4o-mini", "label": "GPT-4o Mini (Multimodal economico)"},
    # GPT-4 Turbo (Legacy)
    {"value": "gpt-4-turbo", "label": "GPT-4 Turbo (Legacy, Vision + 128K)"},
    {"value": "gpt-4", "label": "GPT-4 (Legacy)"},
    # GPT-3.5 (Legacy)
    {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo (Legacy, economico)"},
]

# Provedores de IA disponíveis
AI_PROVIDERS = [
    {"value": "anthropic", "label": "Anthropic (Claude)"},
    {"value": "openai", "label": "OpenAI (GPT)"},
]


class AnthropicModelOption(BaseModel):
    value: str
    label: str


class OpenAIModelOption(BaseModel):
    value: str
    label: str


class AIProviderOption(BaseModel):
    value: str
    label: str


class IntegrationLogResponse(BaseModel):
    """Resposta para logs de integrações"""
    id: int
    integration_type: str  # 'anthropic' or 'serpapi'
    activity: Optional[str] = None
    created_at: datetime

    # Anthropic fields
    model_used: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[Decimal] = None

    # SerpAPI fields
    api_used: Optional[str] = None
    search_url: Optional[str] = None
    product_link: Optional[str] = None

    # Common
    request_data: Optional[Dict[str, Any]] = None
    response_summary: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


# ==================== BATCH QUOTE SCHEMAS ====================

class BatchCreateResponse(BaseModel):
    """Resposta da criacao de um lote de cotacoes"""
    batch_id: int
    total_items: int
    message: str


class BatchQuoteItem(BaseModel):
    """Item de cotacao dentro de um lote"""
    id: int
    status: str
    input_type: Optional[str] = None
    created_at: datetime
    codigo_item: Optional[str] = None
    nome_item: Optional[str] = None
    valor_medio: Optional[Decimal] = None
    batch_index: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class BatchDetailResponse(BaseModel):
    """Detalhes de um lote de cotacoes"""
    id: int
    status: str
    input_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_items: int
    completed_items: int
    failed_items: int
    progress_percentage: float
    project_id: Optional[int] = None
    project: Optional[ProjectInfoResponse] = None
    local: Optional[str] = None
    pesquisador: Optional[str] = None
    error_message: Optional[str] = None
    can_resume: bool = False
    quotes_awaiting_review: int = 0
    quotes_done: int = 0

    class Config:
        from_attributes = True


class BatchListItem(BaseModel):
    """Item resumido de lote para listagem"""
    id: int
    status: str
    input_type: str
    created_at: datetime
    total_items: int
    completed_items: int
    failed_items: int
    progress_percentage: float
    project_id: Optional[int] = None
    project_nome: Optional[str] = None

    class Config:
        from_attributes = True


class BatchListResponse(BaseModel):
    """Lista paginada de lotes"""
    items: List[BatchListItem]
    total: int
    page: int
    per_page: int


class BatchQuotesListResponse(BaseModel):
    """Lista paginada de cotacoes de um lote"""
    items: List[BatchQuoteItem]
    total: int
    page: int
    per_page: int
