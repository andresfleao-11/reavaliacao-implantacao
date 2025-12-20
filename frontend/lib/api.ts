import axios from 'axios'

// Função para obter URL da API com fallback para Railway
const getApiUrl = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL

  // Se tiver variável de ambiente válida com protocolo, usar ela
  if (envUrl && envUrl.startsWith('http')) {
    return envUrl
  }

  // Se estiver no Railway, usar URL do backend de produção
  if (typeof window !== 'undefined' && window.location.hostname.includes('railway.app')) {
    return 'https://backend-production-78bb.up.railway.app'
  }

  // Fallback para desenvolvimento local
  return 'http://localhost:8000'
}

export const API_URL = getApiUrl()

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Interceptor para adicionar o token JWT em todas as requisições
api.interceptors.request.use(
  (config) => {
    // Tentar obter o token do localStorage (apenas no cliente)
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Interceptor para lidar com erros de autenticação
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Se receber 401 Unauthorized, redirecionar para login
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('user')
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export interface QuoteSource {
  id: number
  url: string
  domain: string | null
  page_title: string | null
  price_value: number | null
  currency: string
  extraction_method: string | null
  captured_at: string
  is_outlier: boolean
  is_accepted: boolean
  screenshot_url: string | null
}

export interface ProjectInfo {
  id: number
  nome: string
  cliente_nome: string | null
  config_versao: number | null
}

export interface QuoteAttemptInfo {
  id: number
  attempt_number: number
  status: string
  created_at: string
  error_message: string | null
}

export interface QuoteDetail {
  id: number
  status: string
  input_type: string | null  // TEXT, IMAGE, GOOGLE_LENS
  created_at: string
  input_text: string | null
  codigo_item: string | null
  claude_payload_json: any
  search_query_final: string | null
  local: string | null
  pesquisador: string | null
  valor_medio: number | null
  valor_minimo: number | null
  valor_maximo: number | null
  error_message: string | null
  sources: QuoteSource[]
  pdf_url: string | null
  project_id: number | null
  project: ProjectInfo | null
  current_step: string | null
  progress_percentage: number | null
  step_details: string | null
  // Parâmetros da cotação
  numero_cotacoes_configurado: number | null
  variacao_maxima_percent: number | null
  variacao_percentual: number | null  // Variação calculada = (MAX/MIN - 1) * 100
  // Campos de tentativas
  attempt_number: number
  original_quote_id: number | null
  attempt_history: QuoteAttemptInfo[]
  // ID da cotação filha (se já foi recotado)
  child_quote_id: number | null
  // Lote (se pertence a um lote)
  batch_job_id: number | null
  // JSON do Google Shopping (para debug e consulta)
  google_shopping_response_json: any | null
}

export interface QuoteListItem {
  id: number
  status: string
  input_type: string | null  // TEXT, IMAGE, GOOGLE_LENS
  created_at: string
  codigo_item: string | null
  nome_item: string | null
  valor_medio: number | null
  project_id: number | null
  project_nome: string | null
  cliente_nome: string | null
}

export interface Parameters {
  numero_cotacoes_por_pesquisa: number
  variacao_maxima_percent: number
  pesquisador_padrao: string
  local_padrao: string
  serpapi_location: string
  vigencia_cotacao_veiculos: number  // Vigência em meses para cotações de veículos
  enable_price_mismatch_validation: boolean  // Habilita/desabilita validação de PRICE_MISMATCH
}

export interface SerpApiLocationOption {
  value: string
  label: string
}

export interface BankPrice {
  id: number
  codigo: string
  material: string
  caracteristicas: string | null
  vl_mercado: number | null
  update_mode: string
  updated_at: string
}

export interface RevaluationParams {
  ec_map: Record<string, number>
  pu_map: Record<string, number>
  vuf_map: Record<string, number>
  weights: Record<string, number>
}

export interface IntegrationSetting {
  provider: string
  api_key_masked: string
  other_settings: Record<string, any>
  is_configured: boolean
  source: string | null  // "database" or "environment" or null
}

export interface AnthropicModelOption {
  value: string
  label: string
}

export interface OpenAIModelOption {
  value: string
  label: string
}

export interface AIProviderOption {
  value: string
  label: string
}

export interface MaterialCharacteristic {
  id: number
  nome: string
  descricao: string | null
  tipo_dado: string
  opcoes: string[] | null
  created_at: string
}

export interface SuggestedMaterial {
  id: number
  nome: string
  descricao: string | null
  codigo: string | null
  categoria: string | null
  marca: string | null
  caracteristicas: MaterialCharacteristic[]
  similarity_score: number
  matched_specs: string[]
}

export interface MaterialSuggestionResponse {
  suggestions: SuggestedMaterial[]
  total_found: number
}

export interface BlockedDomain {
  id: number
  domain: string
  display_name: string | null
  reason: string | null
  created_at: string  // ISO datetime string from API
  updated_at: string | null
}

export interface IntegrationLog {
  id: number
  integration_type: 'anthropic' | 'openai' | 'serpapi' | 'search_log' | 'fipe' | 'vehicle_price_bank'
  activity: string | null
  created_at: string
  // Anthropic fields
  model_used: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  estimated_cost_usd: number | null
  // SerpAPI fields
  api_used: string | null
  search_url: string | null
  product_link: string | null
  // Common
  request_data: Record<string, any> | null
  response_summary: Record<string, any> | null
}

export const quotesApi = {
  create: async (formData: FormData) => {
    const response = await api.post('/api/quotes', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  get: async (id: number): Promise<QuoteDetail> => {
    const response = await api.get(`/api/quotes/${id}`)
    return response.data
  },

  list: async (
    page: number = 1,
    perPage: number = 20,
    filters?: {
      quote_id?: number
      search?: string
      status?: string
      project_id?: number
      date_from?: string
      date_to?: string
    }
  ) => {
    const response = await api.get('/api/quotes', {
      params: {
        page,
        per_page: perPage,
        ...filters,
      },
    })
    return response.data
  },

  generatePdf: async (id: number) => {
    const response = await api.post(`/api/quotes/${id}/generate-pdf`)
    return response.data
  },

  downloadPdf: (id: number) => {
    return `${API_URL}/api/quotes/${id}/pdf`
  },

  cancel: async (id: number) => {
    const response = await api.post(`/api/quotes/${id}/cancel`)
    return response.data
  },

  requote: async (id: number) => {
    const response = await api.post(`/api/quotes/${id}/requote`)
    return response.data
  },

  getIntegrationLogs: async (id: number): Promise<IntegrationLog[]> => {
    const response = await api.get(`/api/quotes/${id}/integration-logs`)
    return response.data
  },
}

export const settingsApi = {
  getParameters: async (): Promise<Parameters> => {
    const response = await api.get('/api/settings/parameters')
    return response.data
  },

  updateParameters: async (params: Partial<Parameters>) => {
    const response = await api.put('/api/settings/parameters', params)
    return response.data
  },

  getSerpApiLocations: async (): Promise<SerpApiLocationOption[]> => {
    const response = await api.get('/api/settings/serpapi-locations')
    return response.data
  },

  getAnthropicModels: async (): Promise<AnthropicModelOption[]> => {
    const response = await api.get('/api/settings/anthropic-models')
    return response.data
  },

  getOpenAIModels: async (): Promise<OpenAIModelOption[]> => {
    const response = await api.get('/api/settings/openai-models')
    return response.data
  },

  getAIProviders: async (): Promise<AIProviderOption[]> => {
    const response = await api.get('/api/settings/ai-providers')
    return response.data
  },

  getBankPrices: async (search?: string): Promise<BankPrice[]> => {
    const response = await api.get('/api/settings/bank-prices', {
      params: { search, limit: 100 },
    })
    return response.data
  },

  createBankPrice: async (data: Omit<BankPrice, 'id' | 'updated_at'>) => {
    const response = await api.post('/api/settings/bank-prices', data)
    return response.data
  },

  updateBankPrice: async (codigo: string, data: Partial<BankPrice>) => {
    const response = await api.put(`/api/settings/bank-prices/${codigo}`, data)
    return response.data
  },

  deleteBankPrice: async (codigo: string) => {
    const response = await api.delete(`/api/settings/bank-prices/${codigo}`)
    return response.data
  },

  getRevaluation: async (): Promise<RevaluationParams> => {
    const response = await api.get('/api/settings/revaluation')
    return response.data
  },

  updateRevaluation: async (params: Partial<RevaluationParams>) => {
    const response = await api.put('/api/settings/revaluation', params)
    return response.data
  },

  getIntegration: async (provider: string): Promise<IntegrationSetting> => {
    const response = await api.get(`/api/settings/integrations/${provider}`)
    return response.data
  },

  updateIntegration: async (provider: string, data: { api_key?: string; other_settings?: Record<string, any> }) => {
    const response = await api.put(`/api/settings/integrations/${provider}`, data)
    return response.data
  },

  testIntegration: async (provider: string) => {
    const response = await api.post(`/api/settings/integrations/${provider}/test`)
    return response.data
  },

  getBlockedDomains: async (): Promise<BlockedDomain[]> => {
    const response = await api.get('/api/blocked-domains')
    return response.data
  },

  createBlockedDomain: async (data: { domain: string; display_name?: string; reason?: string }) => {
    const response = await api.post('/api/blocked-domains', data)
    return response.data
  },

  updateBlockedDomain: async (id: number, data: { domain?: string; display_name?: string; reason?: string }) => {
    const response = await api.put(`/api/blocked-domains/${id}`, data)
    return response.data
  },

  deleteBlockedDomain: async (id: number) => {
    const response = await api.delete(`/api/blocked-domains/${id}`)
    return response.data
  },

  generateDomainName: async (domain: string): Promise<{ domain: string; display_name: string }> => {
    const response = await api.post('/api/blocked-domains/generate-name', { domain })
    return response.data
  },
}

export const materialsApi = {
  suggestMaterials: async (
    especificacoes_tecnicas: Record<string, string>,
    tipo_produto?: string,
    project_id?: number
  ): Promise<MaterialSuggestionResponse> => {
    const response = await api.post('/api/materials/suggest', {
      especificacoes_tecnicas,
      tipo_produto,
      project_id,
    })
    return response.data
  },
}

// Google Lens API
export interface LensProduct {
  title: string
  link: string
  source: string
  price: string | null
  extracted_price: number | null
  thumbnail: string | null
  position: number
}

export interface LensSearchResult {
  success: boolean
  total_products: number
  products: LensProduct[]
  image_url: string
  api_calls: any[]
}

export interface LensSpecs {
  nome: string | null
  marca: string | null
  modelo: string | null
  tipo_produto: string | null
  especificacoes: Record<string, any>
  preco: number | null
  url_fonte: string | null
}

export const lensApi = {
  search: async (image: File): Promise<LensSearchResult> => {
    const formData = new FormData()
    formData.append('image', image)
    const response = await api.post('/api/quotes/lens/search', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  extractSpecs: async (productUrl: string): Promise<{ success: boolean; specs: LensSpecs }> => {
    const formData = new FormData()
    formData.append('product_url', productUrl)
    const response = await api.post('/api/quotes/lens/extract-specs', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  createQuote: async (data: {
    product_url: string
    product_title: string
    marca?: string
    modelo?: string
    tipo_produto?: string
    especificacoes?: Record<string, any>
    codigo?: string
    local?: string
    pesquisador?: string
    project_id?: number
    image?: File
    lens_api_calls?: any[]  // API calls from Google Lens search
  }) => {
    const formData = new FormData()
    formData.append('product_url', data.product_url)
    formData.append('product_title', data.product_title)
    if (data.marca) formData.append('marca', data.marca)
    if (data.modelo) formData.append('modelo', data.modelo)
    if (data.tipo_produto) formData.append('tipo_produto', data.tipo_produto)
    if (data.especificacoes) formData.append('especificacoes', JSON.stringify(data.especificacoes))
    if (data.codigo) formData.append('codigo', data.codigo)
    if (data.local) formData.append('local', data.local)
    if (data.pesquisador) formData.append('pesquisador', data.pesquisador)
    if (data.project_id) formData.append('project_id', data.project_id.toString())
    if (data.image) formData.append('image', data.image)
    if (data.lens_api_calls) formData.append('lens_api_calls', JSON.stringify(data.lens_api_calls))

    const response = await api.post('/api/quotes/lens/create-quote', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
}

// ==================== BATCH QUOTES API ====================

export interface BatchQuoteItem {
  id: number
  status: string
  input_type: string | null
  created_at: string
  codigo_item: string | null
  nome_item: string | null
  valor_medio: number | null
  batch_index: number | null
  error_message: string | null
}

export interface BatchJob {
  id: number
  status: string
  input_type: string
  created_at: string
  updated_at: string | null
  total_items: number
  completed_items: number
  failed_items: number
  progress_percentage: number
  project_id: number | null
  project: ProjectInfo | null
  local: string | null
  pesquisador: string | null
  error_message: string | null
  can_resume: boolean
  quotes_awaiting_review: number
  quotes_done: number
}

export interface BatchListItem {
  id: number
  status: string
  input_type: string
  created_at: string
  total_items: number
  completed_items: number
  failed_items: number
  progress_percentage: number
  project_id: number | null
  project_nome: string | null
}

export const batchQuotesApi = {
  createTextBatch: async (data: {
    input_text: string
    local?: string
    pesquisador?: string
    project_id?: number
  }) => {
    const formData = new FormData()
    formData.append('input_text', data.input_text)
    if (data.local) formData.append('local', data.local)
    if (data.pesquisador) formData.append('pesquisador', data.pesquisador)
    if (data.project_id) formData.append('project_id', data.project_id.toString())

    const response = await api.post('/api/batch-quotes/text', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  createImageBatch: async (data: {
    images: File[]
    local?: string
    pesquisador?: string
    project_id?: number
  }) => {
    const formData = new FormData()
    data.images.forEach(img => formData.append('images', img))
    if (data.local) formData.append('local', data.local)
    if (data.pesquisador) formData.append('pesquisador', data.pesquisador)
    if (data.project_id) formData.append('project_id', data.project_id.toString())

    const response = await api.post('/api/batch-quotes/images', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  createFileBatch: async (data: {
    file: File
    local?: string
    pesquisador?: string
    project_id?: number
  }) => {
    const formData = new FormData()
    formData.append('file', data.file)
    if (data.local) formData.append('local', data.local)
    if (data.pesquisador) formData.append('pesquisador', data.pesquisador)
    if (data.project_id) formData.append('project_id', data.project_id.toString())

    const response = await api.post('/api/batch-quotes/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  getBatch: async (id: number): Promise<BatchJob> => {
    const response = await api.get(`/api/batch-quotes/${id}`)
    return response.data
  },

  getBatchQuotes: async (id: number, page: number = 1, perPage: number = 20, status?: string) => {
    const response = await api.get(`/api/batch-quotes/${id}/quotes`, {
      params: { page, per_page: perPage, status },
    })
    return response.data
  },

  cancelBatch: async (id: number) => {
    const response = await api.post(`/api/batch-quotes/${id}/cancel`)
    return response.data
  },

  resumeBatch: async (id: number) => {
    const response = await api.post(`/api/batch-quotes/${id}/resume`)
    return response.data
  },

  listBatches: async (
    page: number = 1,
    perPage: number = 20,
    filters?: {
      batch_id?: number
      project_id?: number
      client_id?: number
      input_type?: string
      status?: string
    }
  ) => {
    const response = await api.get('/api/batch-quotes', {
      params: {
        page,
        per_page: perPage,
        ...filters,
      },
    })
    return response.data
  },

  getBatchCosts: async (id: number): Promise<BatchCosts> => {
    const response = await api.get(`/api/batch-quotes/${id}/costs`)
    return response.data
  },

  // Gerar URLs de download para ZIP e Excel
  getDownloadZipUrl: (id: number): string => {
    return `${API_URL}/api/batch-quotes/${id}/download/zip`
  },

  getDownloadExcelUrl: (id: number): string => {
    return `${API_URL}/api/batch-quotes/${id}/download/excel`
  },

  // Regenerar arquivos de resultado
  generateResults: async (id: number) => {
    const response = await api.post(`/api/batch-quotes/${id}/generate-results`)
    return response.data
  },
}

export interface BatchCosts {
  batch_id: number
  anthropic: {
    calls: number
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
  }
  serpapi: {
    calls: number
    google_shopping: number
    immersive_product: number
    cost_usd?: number
  }
  total_cost_usd: number
  total_cost_brl: number
}

// ==================== VEHICLE PRICES API ====================

export interface VehiclePrice {
  id: number
  created_at: string
  updated_at: string
  codigo_fipe: string
  brand_id: number
  brand_name: string
  model_id: number
  model_name: string
  year_id: string
  year_model: number
  fuel_type: string
  fuel_code: number
  vehicle_type: string
  vehicle_name: string
  price_value: number
  reference_month: string
  reference_date: string
  status: 'Vigente' | 'Expirada' | 'Pendente'  // Status: Vigente, Expirada ou Pendente (sem screenshot)
  has_screenshot: boolean  // Indica se tem screenshot da consulta FIPE
  quote_request_id: number | null
  last_api_call: string | null
}

export interface VehiclePriceListResponse {
  items: VehiclePrice[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface RefreshPriceResponse {
  success: boolean
  message: string
  vehicle?: VehiclePrice
  new_price?: number
  old_price?: number
  reference_month?: string
}

export interface BulkRefreshResponse {
  total: number
  success_count: number
  error_count: number
  errors: string[]
}

export const vehiclePricesApi = {
  list: async (params: {
    page?: number
    page_size?: number
    brand_name?: string
    model_name?: string
    year_model?: number
    codigo_fipe?: string
    reference_month?: string
    vehicle_type?: string
    status?: 'Vigente' | 'Expirada' | 'Pendente'  // Filtro por status de vigência ou screenshot pendente
    has_screenshot?: boolean  // Filtro por presença de screenshot
    sort_by?: string
    sort_order?: string
  }): Promise<VehiclePriceListResponse> => {
    const response = await api.get('/api/vehicle-prices', { params })
    return response.data
  },

  get: async (id: number): Promise<VehiclePrice> => {
    const response = await api.get(`/api/vehicle-prices/${id}`)
    return response.data
  },

  refresh: async (id: number): Promise<RefreshPriceResponse> => {
    const response = await api.post(`/api/vehicle-prices/${id}/refresh`)
    return response.data
  },

  retryScreenshot: async (id: number): Promise<{ success: boolean; message: string; screenshot_url?: string }> => {
    const response = await api.post(`/api/vehicle-prices/${id}/retry-screenshot`)
    return response.data
  },

  getScreenshotUrl: (id: number): string => {
    return `${API_URL}/api/vehicle-prices/${id}/screenshot`
  },

  refreshAll: async (params?: {
    vehicle_type?: string
    brand_name?: string
  }): Promise<BulkRefreshResponse> => {
    const response = await api.post('/api/vehicle-prices/refresh-all', null, { params })
    return response.data
  },

  getBrands: async (): Promise<string[]> => {
    const response = await api.get('/api/vehicle-prices/filters/brands')
    return response.data
  },

  getYears: async (): Promise<number[]> => {
    const response = await api.get('/api/vehicle-prices/filters/years')
    return response.data
  },

  getReferenceMonths: async (): Promise<string[]> => {
    const response = await api.get('/api/vehicle-prices/filters/reference-months')
    return response.data
  },

  exportCSV: async (params?: {
    brand_name?: string
    year_model?: number
    reference_month?: string
    status?: 'Vigente' | 'Expirada' | 'Pendente'
  }): Promise<void> => {
    const queryParams = new URLSearchParams()
    if (params?.brand_name) queryParams.append('brand_name', params.brand_name)
    if (params?.year_model) queryParams.append('year_model', String(params.year_model))
    if (params?.reference_month) queryParams.append('reference_month', params.reference_month)
    if (params?.status) queryParams.append('status', params.status)

    const url = `/api/vehicle-prices/export/csv${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    const response = await api.get(url, { responseType: 'blob' })

    // Criar link para download
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const urlBlob = window.URL.createObjectURL(blob)
    link.href = urlBlob

    // Extrair nome do arquivo do header ou usar padrão
    const contentDisposition = response.headers['content-disposition']
    let filename = `banco_precos_veiculos_${new Date().toISOString().split('T')[0]}.csv`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/)
      if (match) filename = match[1]
    }

    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(urlBlob)
  },
}

// ==================== INVENTORY - EXTERNAL SYSTEMS API ====================

export interface ExternalSystem {
  id: number
  name: string
  system_type: string
  host: string
  port: number | null
  context_path: string | null
  full_url: string | null
  auth_type: string
  auth_username: string | null
  is_active: boolean
  is_default: boolean
  timeout_seconds: number
  retry_attempts: number
  double_json_encoding: boolean
  last_test_at: string | null
  last_test_success: boolean | null
  last_test_message: string | null
  last_sync_at: string | null
  created_at: string
}

export interface ExternalSystemCreate {
  name: string
  system_type: string
  host: string
  port?: number
  context_path?: string
  full_url?: string
  auth_type: string
  auth_username?: string
  auth_password?: string
  auth_token?: string
  auth_header_name?: string
  timeout_seconds?: number
  retry_attempts?: number
  double_json_encoding?: boolean
  is_default?: boolean
}

export interface ConnectionTestResult {
  success: boolean
  message: string
  response_time_ms?: number
  server_info?: any
  error_details?: string
}

export interface SyncResult {
  received: number
  created: number
  updated: number
  failed: number
}

export interface MasterDataItem {
  id: number
  code: string
  name: string
  extra_data?: any
  synced_at: string
}

export const externalSystemsApi = {
  list: async (): Promise<ExternalSystem[]> => {
    const response = await api.get('/api/inventory/systems')
    // API returns {items: [...], total: N}
    return response.data.items || response.data
  },

  get: async (id: number): Promise<ExternalSystem> => {
    const response = await api.get(`/api/inventory/systems/${id}`)
    return response.data
  },

  create: async (data: ExternalSystemCreate): Promise<ExternalSystem> => {
    const response = await api.post('/api/inventory/systems', data)
    return response.data
  },

  update: async (id: number, data: Partial<ExternalSystemCreate>): Promise<ExternalSystem> => {
    const response = await api.put(`/api/inventory/systems/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/inventory/systems/${id}`)
  },

  testConnection: async (id: number): Promise<ConnectionTestResult> => {
    const response = await api.post(`/api/inventory/systems/${id}/test`)
    return response.data
  },

  testUrl: async (data: {
    host: string
    port?: number
    context_path?: string
    full_url?: string
    auth_type: string
    auth_username?: string
    auth_password?: string
    auth_token?: string
    auth_header_name?: string
    timeout_seconds?: number
    double_json_encoding?: boolean
  }): Promise<ConnectionTestResult> => {
    const response = await api.post('/api/inventory/systems/test-url', data)
    return response.data
  },

  sync: async (id: number): Promise<Record<string, SyncResult>> => {
    const response = await api.post(`/api/inventory/systems/${id}/sync`)
    return response.data
  },

  syncUGs: async (id: number): Promise<SyncResult> => {
    const response = await api.post(`/api/inventory/systems/${id}/sync/ug`)
    return response.data
  },

  syncULs: async (id: number): Promise<SyncResult> => {
    const response = await api.post(`/api/inventory/systems/${id}/sync/ul`)
    return response.data
  },

  getUGs: async (id: number): Promise<MasterDataItem[]> => {
    const response = await api.get(`/api/inventory/systems/${id}/ug`)
    return response.data
  },

  getULs: async (id: number, ugId?: number): Promise<MasterDataItem[]> => {
    const response = await api.get(`/api/inventory/systems/${id}/ul`, {
      params: ugId ? { ug_id: ugId } : undefined
    })
    return response.data
  },

  getSyncLogs: async (id: number): Promise<any[]> => {
    const response = await api.get(`/api/inventory/systems/${id}/sync-logs`)
    return response.data
  },
}

// ==================== INVENTORY - SESSIONS API ====================

export interface InventorySession {
  id: number
  code: string
  name: string | null
  description: string | null
  status: string
  project: {
    id: number
    name: string
    inventory_config?: any
  } | null
  ug: { id: number; code: string; name: string } | null
  ul: { id: number; code: string; name: string } | null
  ua: { id: number; code: string; name: string } | null
  statistics: {
    total_expected: number
    total_found: number
    total_not_found: number
    total_unregistered: number
    total_written_off: number
    completion_percentage: number
  }
  scheduled_start: string | null
  scheduled_end: string | null
  started_at: string | null
  completed_at: string | null
  created_by: { id: number; name: string } | null
  created_at: string
  updated_at: string | null
}

export interface InventorySessionCreate {
  project_id: number
  name: string
  description?: string
  ug_id?: number
  ul_id?: number
  ua_id?: number
  scheduled_start?: string
  scheduled_end?: string
}

export interface ExpectedAsset {
  id: number
  asset_code: string
  description: string | null
  rfid_code: string | null
  barcode: string | null
  category: string | null
  expected_ul_code: string | null
  expected_ua_code: string | null
  is_written_off: boolean
  extra_data: any
  verified: boolean
  reading: {
    id: number
    category: string
    read_method: string
    physical_condition: string | null
    read_at: string
  } | null
}

export interface AssetReading {
  id: number
  asset_code: string
  rfid_code: string | null
  barcode: string | null
  category: string
  read_method: string
  physical_condition: string | null
  notes: string | null
  read_latitude: number | null
  read_longitude: number | null
  read_at: string
  expected_asset: {
    id: number
    description: string
    rfid_code: string | null
  } | null
}

export interface SessionStatistics {
  total_expected: number
  total_found: number
  total_not_found: number
  total_unregistered: number
  total_written_off: number
  completion_percentage: number
  by_method?: Record<string, number>
  by_condition?: Record<string, number>
}

export const inventorySessionsApi = {
  list: async (params?: {
    project_id?: number
    status?: string
    skip?: number
    limit?: number
  }): Promise<{ total: number; items: InventorySession[] }> => {
    const response = await api.get('/api/inventory/sessions', { params })
    return response.data
  },

  get: async (id: number): Promise<InventorySession> => {
    const response = await api.get(`/api/inventory/sessions/${id}`)
    return response.data
  },

  create: async (data: InventorySessionCreate): Promise<{ id: number; code: string; name: string; status: string; message: string }> => {
    const response = await api.post('/api/inventory/sessions', data)
    return response.data
  },

  update: async (id: number, data: Partial<InventorySessionCreate & { status?: string }>): Promise<{ message: string }> => {
    const response = await api.put(`/api/inventory/sessions/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/inventory/sessions/${id}`)
  },

  start: async (id: number): Promise<{ message: string; started_at: string }> => {
    const response = await api.post(`/api/inventory/sessions/${id}/start`)
    return response.data
  },

  pause: async (id: number): Promise<{ message: string }> => {
    const response = await api.post(`/api/inventory/sessions/${id}/pause`)
    return response.data
  },

  complete: async (id: number): Promise<{ message: string; statistics: SessionStatistics; completed_at: string }> => {
    const response = await api.post(`/api/inventory/sessions/${id}/complete`)
    return response.data
  },

  // Expected Assets
  listExpectedAssets: async (sessionId: number, params?: {
    search?: string
    verified?: boolean
    skip?: number
    limit?: number
  }): Promise<{ total: number; items: ExpectedAsset[] }> => {
    const response = await api.get(`/api/inventory/sessions/${sessionId}/expected`, { params })
    return response.data
  },

  addExpectedAsset: async (sessionId: number, data: {
    asset_code: string
    description: string
    rfid_code?: string
    barcode?: string
    category?: string
    expected_ul_code?: string
    expected_ua_code?: string
    extra_data?: any
  }): Promise<{ id: number; message: string }> => {
    const response = await api.post(`/api/inventory/sessions/${sessionId}/expected`, data)
    return response.data
  },

  uploadExpectedAssets: async (sessionId: number, file: File): Promise<{
    message: string
    created: number
    updated: number
    errors: string[]
  }> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post(`/api/inventory/sessions/${sessionId}/expected/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  syncExpectedAssets: async (sessionId: number, options?: {
    limit?: number
    clear_existing?: boolean
  }): Promise<{
    success: boolean
    message: string
    system: string
    statistics: {
      received: number
      mapped: number
      created: number
      updated: number
      failed: number
      total_expected: number
    }
    errors?: string[]
  }> => {
    const response = await api.post(`/api/inventory/sessions/${sessionId}/expected/sync`, options || {})
    return response.data
  },

  uploadResults: async (sessionId: number, options?: {
    include_photos?: boolean
  }): Promise<{
    success: boolean
    message: string
    system: string
    transmission_number: string
    inventory_id: string
    items_sent: number
  }> => {
    const response = await api.post(`/api/inventory/sessions/${sessionId}/upload`, options || {})
    return response.data
  },

  // Readings
  listReadings: async (sessionId: number, params?: {
    category?: string
    skip?: number
    limit?: number
  }): Promise<{ total: number; items: AssetReading[] }> => {
    const response = await api.get(`/api/inventory/sessions/${sessionId}/readings`, { params })
    return response.data
  },

  registerReading: async (sessionId: number, data: {
    identifier: string
    read_method?: string
    physical_condition?: string
    physical_status_id?: number
    observations?: string
    photo_file_id?: number
    latitude?: number
    longitude?: number
  }): Promise<{
    id: number
    category: string
    message: string
    expected_asset: { id: number; description: string } | null
  }> => {
    const response = await api.post(`/api/inventory/sessions/${sessionId}/readings`, data)
    return response.data
  },

  registerBulkReadings: async (sessionId: number, readings: Array<{
    identifier: string
    read_method?: string
  }>): Promise<{
    found: number
    unregistered: number
    updated: number
    errors: string[]
  }> => {
    const response = await api.post(`/api/inventory/sessions/${sessionId}/readings/bulk`, { readings })
    return response.data
  },

  updateReadingCategory: async (sessionId: number, readingId: number, data: {
    category: string
    notes?: string
  }): Promise<{ message: string }> => {
    const response = await api.put(`/api/inventory/sessions/${sessionId}/readings/${readingId}/category`, data)
    return response.data
  },

  // Statistics
  getStatistics: async (sessionId: number): Promise<SessionStatistics> => {
    const response = await api.get(`/api/inventory/sessions/${sessionId}/statistics`)
    return response.data
  },
}
