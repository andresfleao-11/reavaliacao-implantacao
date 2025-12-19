'use client'

import { useState, useEffect } from 'react'
import { settingsApi, IntegrationSetting, AnthropicModelOption, OpenAIModelOption, AIProviderOption, API_URL, api } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

// Tabs
type TabType = 'apis' | 'middleware'

interface MiddlewareToken {
  token: string
  expires_at: string
  user_id: number
  user_name: string
  server_url: string
  device_name: string
}

interface MiddlewareConfig {
  server_url: string
  api_version: string
  endpoints: Record<string, string>
}

export default function IntegracoesPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'ADMIN'
  const [activeTab, setActiveTab] = useState<TabType>('apis')

  // API Integration States
  const [serpApiKey, setSerpApiKey] = useState('')
  const [anthropicApiKey, setAnthropicApiKey] = useState('')
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [imgbbApiKey, setImgbbApiKey] = useState('')
  const [fipeApiKey, setFipeApiKey] = useState('')
  const [fipeApiType, setFipeApiType] = useState<'public' | 'private'>('public')
  const [serpApiStatus, setSerpApiStatus] = useState<IntegrationSetting | null>(null)
  const [anthropicStatus, setAnthropicStatus] = useState<IntegrationSetting | null>(null)
  const [openaiStatus, setOpenaiStatus] = useState<IntegrationSetting | null>(null)
  const [imgbbStatus, setImgbbStatus] = useState<IntegrationSetting | null>(null)
  const [fipeStatus, setFipeStatus] = useState<IntegrationSetting | null>(null)
  const [anthropicModels, setAnthropicModels] = useState<AnthropicModelOption[]>([])
  const [openaiModels, setOpenaiModels] = useState<OpenAIModelOption[]>([])
  const [aiProviders, setAIProviders] = useState<AIProviderOption[]>([])
  const [selectedAnthropicModel, setSelectedAnthropicModel] = useState('')
  const [selectedOpenaiModel, setSelectedOpenaiModel] = useState('')
  const [selectedAIProvider, setSelectedAIProvider] = useState('anthropic')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [integrationMessages, setIntegrationMessages] = useState<Record<string, { type: 'success' | 'error', text: string }>>({})
  const [loading, setLoading] = useState(true)

  // SerpAPI cost config
  const [serpApiCostPerCall, setSerpApiCostPerCall] = useState('')
  const [serpApiCostConfig, setSerpApiCostConfig] = useState<{ cost_per_call: number | null; updated_at: string | null } | null>(null)

  // USD to BRL exchange rate (read-only, auto-updated from BCB)
  const [exchangeRateConfig, setExchangeRateConfig] = useState<{
    rate: number | null;
    source: string | null;
    updated_at: string | null;
    bcb_date: string | null;
  } | null>(null)
  const [updatingExchangeRate, setUpdatingExchangeRate] = useState(false)
  const [testingBCB, setTestingBCB] = useState(false)

  // Middleware States
  const [middlewareConfig, setMiddlewareConfig] = useState<MiddlewareConfig | null>(null)
  const [generatedToken, setGeneratedToken] = useState<MiddlewareToken | null>(null)
  const [deviceName, setDeviceName] = useState('RFID Middleware')
  const [tokenExpiresDays, setTokenExpiresDays] = useState(365)
  const [generatingToken, setGeneratingToken] = useState(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  useEffect(() => {
    const loadAll = async () => {
      await loadIntegrationStatus()
      await loadModels()
    }
    loadAll()
    loadCostConfig()
    loadMiddlewareConfig()
  }, [])

  const loadMiddlewareConfig = async () => {
    try {
      const response = await api.get('/api/users/middleware-config')
      setMiddlewareConfig(response.data)
    } catch (err) {
      console.error('Error loading middleware config:', err)
    }
  }

  const generateMiddlewareToken = async () => {
    setGeneratingToken(true)
    try {
      const response = await api.post('/api/users/middleware-token', {
        name: deviceName,
        expires_days: tokenExpiresDays
      })
      setGeneratedToken(response.data)
      setIntegrationMessage('MIDDLEWARE', 'success', 'Token gerado com sucesso!')
    } catch (err) {
      setIntegrationMessage('MIDDLEWARE', 'error', 'Erro ao gerar token')
    } finally {
      setGeneratingToken(false)
    }
  }

  const copyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const loadCostConfig = async () => {
    try {
      const res = await fetch(`${API_URL}/api/settings/cost-config`)
      const data = await res.json()
      if (data.serpapi_cost_per_call) {
        setSerpApiCostPerCall(data.serpapi_cost_per_call.toString())
        setSerpApiCostConfig({
          cost_per_call: data.serpapi_cost_per_call,
          updated_at: data.serpapi_updated_at
        })
      }
      // Load exchange rate from dedicated endpoint
      const exchangeRes = await fetch(`${API_URL}/api/settings/exchange-rate`)
      const exchangeData = await exchangeRes.json()
      setExchangeRateConfig({
        rate: exchangeData.rate,
        source: exchangeData.source,
        updated_at: exchangeData.updated_at,
        bcb_date: exchangeData.bcb_date
      })
    } catch (err) {
      console.error('Error loading cost config:', err)
    }
  }

  const handleUpdateExchangeRate = async () => {
    setUpdatingExchangeRate(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n['EXCHANGE']; return n })
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`${API_URL}/api/settings/exchange-rate/update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setIntegrationMessage('EXCHANGE', 'success', `Taxa atualizada: USD 1 = R$ ${data.rate.toFixed(4)}`)
        await loadCostConfig()
      } else {
        setIntegrationMessage('EXCHANGE', 'error', data.detail || 'Erro ao atualizar taxa de cambio')
      }
    } catch (err) {
      setIntegrationMessage('EXCHANGE', 'error', 'Erro ao conectar com o servidor')
    } finally {
      setUpdatingExchangeRate(false)
    }
  }

  const handleTestBCB = async () => {
    setTestingBCB(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n['BCB']; return n })
    try {
      const res = await fetch(`${API_URL}/api/settings/integrations/bcb/test`, {
        method: 'POST'
      })
      const data = await res.json()
      setIntegrationMessage('BCB', data.success ? 'success' : 'error',
        data.success ? `OK ${data.message}` : `ERRO ${data.message}`)
    } catch (err) {
      setIntegrationMessage('BCB', 'error', 'Erro ao testar conexao com BCB')
    } finally {
      setTestingBCB(false)
    }
  }

  const loadIntegrationStatus = async () => {
    setLoading(true)
    try {
      const [serpResult, anthropicResult, openaiResult, imgbbResult, fipeResult] = await Promise.all([
        settingsApi.getIntegration('SERPAPI').catch(() => null),
        settingsApi.getIntegration('ANTHROPIC').catch(() => null),
        settingsApi.getIntegration('OPENAI').catch(() => null),
        settingsApi.getIntegration('IMGBB').catch(() => null),
        settingsApi.getIntegration('FIPE').catch(() => null)
      ])
      setSerpApiStatus(serpResult)
      setAnthropicStatus(anthropicResult)
      setOpenaiStatus(openaiResult)
      setImgbbStatus(imgbbResult)
      setFipeStatus(fipeResult)

      // Set FIPE API type from settings
      if (fipeResult?.other_settings?.api_type) {
        setFipeApiType(fipeResult.other_settings.api_type)
      }

      // Set current models from other_settings
      if (anthropicResult?.other_settings?.model) {
        setSelectedAnthropicModel(anthropicResult.other_settings.model)
      }
      if (openaiResult?.other_settings?.model) {
        setSelectedOpenaiModel(openaiResult.other_settings.model)
      }
      // Set AI provider from settings
      if (anthropicResult?.other_settings?.ai_provider) {
        setSelectedAIProvider(anthropicResult.other_settings.ai_provider)
      } else if (openaiResult?.other_settings?.ai_provider) {
        setSelectedAIProvider(openaiResult.other_settings.ai_provider)
      }
    } catch (err) {
      console.error('Error loading integration status:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadModels = async () => {
    try {
      const [anthropic, openai, providers] = await Promise.all([
        settingsApi.getAnthropicModels(),
        settingsApi.getOpenAIModels(),
        settingsApi.getAIProviders()
      ])
      setAnthropicModels(anthropic)
      setOpenaiModels(openai)
      setAIProviders(providers)

      // Set default models if not already set
      if (!selectedAnthropicModel && anthropic.length > 0) {
        setSelectedAnthropicModel(anthropic[0].value)
      }
      if (!selectedOpenaiModel && openai.length > 0) {
        setSelectedOpenaiModel(openai[0].value)
      }
    } catch (err) {
      console.error('Error loading models:', err)
    }
  }

  const setIntegrationMessage = (provider: string, type: 'success' | 'error', text: string) => {
    setIntegrationMessages(prev => ({ ...prev, [provider]: { type, text } }))
    // Auto-limpar mensagem apos 5 segundos
    setTimeout(() => {
      setIntegrationMessages(prev => {
        const newMessages = { ...prev }
        delete newMessages[provider]
        return newMessages
      })
    }, 5000)
  }

  const handleSaveSerpApiCost = async () => {
    setSaving(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n['SERPAPI_COST']; return n })
    try {
      const costValue = parseFloat(serpApiCostPerCall)
      if (isNaN(costValue) || costValue <= 0) {
        setIntegrationMessage('SERPAPI', 'error', 'Informe um valor valido para o custo por chamada')
        return
      }
      await fetch(`${API_URL}/api/settings/cost-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serpapi_cost_per_call: costValue })
      })
      setIntegrationMessage('SERPAPI', 'success', `Custo SerpAPI atualizado: R$ ${costValue.toFixed(4)}/chamada`)
      await loadCostConfig()
    } catch (err) {
      setIntegrationMessage('SERPAPI', 'error', 'Erro ao salvar custo SerpAPI')
    } finally {
      setSaving(false)
    }
  }

  const handleSave = async (provider: string, apiKey: string) => {
    setSaving(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n[provider]; return n })
    try {
      await settingsApi.updateIntegration(provider, { api_key: apiKey })
      setIntegrationMessage(provider, 'success', `${provider} atualizado com sucesso!`)
      await loadIntegrationStatus()
      if (provider === 'SERPAPI') setSerpApiKey('')
      if (provider === 'IMGBB') setImgbbApiKey('')
      if (provider === 'FIPE') setFipeApiKey('')
    } catch (err) {
      setIntegrationMessage(provider, 'error', `Erro ao atualizar ${provider}`)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveAnthropic = async () => {
    setSaving(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n['ANTHROPIC']; return n })
    try {
      const updateData: { api_key?: string; other_settings?: Record<string, any> } = {}

      if (anthropicApiKey) {
        updateData.api_key = anthropicApiKey
      }

      updateData.other_settings = {
        model: selectedAnthropicModel,
        ai_provider: selectedAIProvider
      }

      await settingsApi.updateIntegration('ANTHROPIC', updateData)
      setIntegrationMessage('ANTHROPIC', 'success', 'Anthropic atualizado com sucesso!')
      await loadIntegrationStatus()
      setAnthropicApiKey('')
    } catch (err) {
      setIntegrationMessage('ANTHROPIC', 'error', 'Erro ao atualizar Anthropic')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveOpenAI = async () => {
    setSaving(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n['OPENAI']; return n })
    try {
      const updateData: { api_key?: string; other_settings?: Record<string, any> } = {}

      if (openaiApiKey) {
        updateData.api_key = openaiApiKey
      }

      updateData.other_settings = {
        model: selectedOpenaiModel,
        ai_provider: selectedAIProvider
      }

      await settingsApi.updateIntegration('OPENAI', updateData)
      setIntegrationMessage('OPENAI', 'success', 'OpenAI atualizado com sucesso!')
      await loadIntegrationStatus()
      setOpenaiApiKey('')
    } catch (err) {
      setIntegrationMessage('OPENAI', 'error', 'Erro ao atualizar OpenAI')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveFipe = async () => {
    setSaving(true)
    setIntegrationMessages(prev => { const n = {...prev}; delete n['FIPE']; return n })
    try {
      const updateData: { api_key?: string; other_settings?: Record<string, any> } = {
        other_settings: { api_type: fipeApiType }
      }

      // Se for API privada e tiver chave, ou se quiser atualizar a chave
      if (fipeApiKey) {
        updateData.api_key = fipeApiKey
      } else if (fipeApiType === 'public') {
        // Para API publica, usar uma chave placeholder
        updateData.api_key = 'PUBLIC_API'
      }

      await settingsApi.updateIntegration('FIPE', updateData)
      setIntegrationMessage('FIPE', 'success', 'API FIPE configurada com sucesso!')
      await loadIntegrationStatus()
      setFipeApiKey('')
    } catch (err) {
      setIntegrationMessage('FIPE', 'error', 'Erro ao configurar API FIPE')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveAIProvider = async () => {
    setSaving(true)
    setMessage('')
    try {
      // Save to both providers to keep in sync
      await Promise.all([
        settingsApi.updateIntegration('ANTHROPIC', { other_settings: { ai_provider: selectedAIProvider } }),
        settingsApi.updateIntegration('OPENAI', { other_settings: { ai_provider: selectedAIProvider } })
      ])
      setMessage(`Provedor de IA alterado para ${selectedAIProvider === 'anthropic' ? 'Anthropic (Claude)' : 'OpenAI (GPT)'}!`)
      await loadIntegrationStatus()
    } catch (err) {
      setMessage('Erro ao alterar provedor de IA')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (provider: string) => {
    setTesting(provider)
    setIntegrationMessages(prev => { const n = {...prev}; delete n[provider]; return n })
    try {
      const result = await settingsApi.testIntegration(provider)
      setIntegrationMessage(provider, result.success ? 'success' : 'error', result.success ? `OK ${result.message}` : `ERRO ${result.message}`)
    } catch (err) {
      setIntegrationMessage(provider, 'error', `Erro ao testar ${provider}`)
    } finally {
      setTesting(null)
    }
  }

  const renderIntegrationMessage = (provider: string) => {
    const msg = integrationMessages[provider]
    if (!msg) return null
    return (
      <div className={`mb-4 px-4 py-3 rounded-lg ${msg.type === 'success' ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}`}>
        {msg.text}
      </div>
    )
  }

  const renderStatusBadge = (status: IntegrationSetting | null) => {
    if (!status) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300">
          Nao configurado
        </span>
      )
    }
    if (status.is_configured) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
          Configurado ({status.source === 'environment' ? 'variavel de ambiente' : 'banco de dados'})
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300">
        Nao configurado
      </span>
    )
  }

  if (loading) {
    return (
      <div className="max-w-4xl">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-8">Integracoes</h1>
        <div className="text-gray-500 dark:text-gray-400">Carregando...</div>
      </div>
    )
  }

  // Render Middleware Tab Content
  const renderMiddlewareTab = () => (
    <div className="space-y-6">
      {/* Server Configuration */}
      <div className="card bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border-2 border-blue-200 dark:border-blue-800">
        <div className="flex items-center mb-4">
          <svg className="w-6 h-6 mr-2 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
          </svg>
          <h2 className="text-xl font-semibold text-blue-900 dark:text-blue-100">Configuracoes do Servidor</h2>
        </div>
        <p className="text-sm text-blue-700 dark:text-blue-300 mb-4">
          Use estas configuracoes no aplicativo RFID Middleware para conectar ao servidor.
        </p>

        <div className="space-y-4">
          {/* Server URL */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              URL do Servidor
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={middlewareConfig?.server_url || API_URL}
                readOnly
                className="input-field flex-1 bg-gray-50 dark:bg-gray-700"
              />
              <button
                onClick={() => copyToClipboard(middlewareConfig?.server_url || API_URL, 'server_url')}
                className="btn-secondary flex items-center gap-1"
              >
                {copiedField === 'server_url' ? (
                  <>
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Copiado!
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                    </svg>
                    Copiar
                  </>
                )}
              </button>
            </div>
          </div>

          {/* API Version */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Versao da API
            </label>
            <input
              type="text"
              value={middlewareConfig?.api_version || '1.0'}
              readOnly
              className="input-field w-32 bg-gray-50 dark:bg-gray-700"
            />
          </div>
        </div>
      </div>

      {/* Token Generation */}
      <div className="card">
        {renderIntegrationMessage('MIDDLEWARE')}
        <div className="flex items-center mb-4">
          <svg className="w-6 h-6 mr-2 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Gerar Token de Acesso</h2>
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Gere um token de autenticacao para usar no aplicativo RFID Middleware. O token sera vinculado a sua conta.
        </p>

        <div className="space-y-4">
          {/* Device Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Nome do Dispositivo
            </label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              className="input-field w-full"
              placeholder="Ex: RFID Middleware - Coletor 1"
            />
          </div>

          {/* Expiration */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Validade do Token (dias)
            </label>
            <select
              value={tokenExpiresDays}
              onChange={(e) => setTokenExpiresDays(Number(e.target.value))}
              className="input-field w-48"
            >
              <option value={30}>30 dias</option>
              <option value={90}>90 dias</option>
              <option value={180}>180 dias</option>
              <option value={365}>1 ano</option>
              <option value={730}>2 anos</option>
            </select>
          </div>

          {/* Generate Button */}
          <button
            onClick={generateMiddlewareToken}
            disabled={generatingToken || !deviceName}
            className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generatingToken ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Gerando...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Gerar Token
              </>
            )}
          </button>
        </div>

        {/* Generated Token Display */}
        {generatedToken && (
          <div className="mt-6 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <h3 className="font-semibold text-green-800 dark:text-green-200 mb-3 flex items-center">
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Token Gerado com Sucesso!
            </h3>

            <div className="space-y-3">
              {/* Token */}
              <div>
                <label className="block text-xs font-medium text-green-700 dark:text-green-300 mb-1">Token de Autenticacao</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={generatedToken.token}
                    readOnly
                    className="input-field flex-1 text-xs font-mono bg-white dark:bg-gray-800"
                  />
                  <button
                    onClick={() => copyToClipboard(generatedToken.token, 'token')}
                    className="btn-secondary flex items-center gap-1 whitespace-nowrap"
                  >
                    {copiedField === 'token' ? (
                      <>
                        <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Copiado!
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                        </svg>
                        Copiar
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-green-700 dark:text-green-300 font-medium">Usuario:</span>
                  <span className="ml-2 text-green-900 dark:text-green-100">{generatedToken.user_name}</span>
                </div>
                <div>
                  <span className="text-green-700 dark:text-green-300 font-medium">Dispositivo:</span>
                  <span className="ml-2 text-green-900 dark:text-green-100">{generatedToken.device_name}</span>
                </div>
                <div>
                  <span className="text-green-700 dark:text-green-300 font-medium">Expira em:</span>
                  <span className="ml-2 text-green-900 dark:text-green-100">
                    {new Date(generatedToken.expires_at).toLocaleDateString('pt-BR')}
                  </span>
                </div>
                <div>
                  <span className="text-green-700 dark:text-green-300 font-medium">Servidor:</span>
                  <span className="ml-2 text-green-900 dark:text-green-100">{generatedToken.server_url}</span>
                </div>
              </div>

              <div className="mt-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-700">
                <p className="text-sm text-yellow-800 dark:text-yellow-200">
                  <strong>Importante:</strong> Copie o token agora. Por seguranca, ele nao sera exibido novamente.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="card bg-gray-50 dark:bg-gray-800">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center">
          <svg className="w-5 h-5 mr-2 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Como Configurar o App RFID Middleware
        </h3>
        <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700 dark:text-gray-300">
          <li>Abra o aplicativo RFID Middleware no dispositivo</li>
          <li>Acesse <strong>Configuracoes</strong> no menu</li>
          <li>Cole a <strong>URL do Servidor</strong> no campo correspondente</li>
          <li>Cole o <strong>Token de Autenticacao</strong> gerado acima</li>
          <li>Salve as configuracoes e teste a conexao</li>
        </ol>
      </div>
    </div>
  )

  // Render APIs Tab Content (existing content)
  const renderApisTab = () => (
    <div className="space-y-6">
      {!isAdmin && (
        <div className="mb-6 px-4 py-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300">
          <div className="flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="font-medium">Acesso somente leitura.</span>
            <span className="ml-1">Apenas administradores podem alterar as configuracoes de integracao.</span>
          </div>
        </div>
      )}

      {message && (
        <div className={`mb-6 px-4 py-3 rounded-lg ${message.includes('OK') || message.includes('sucesso') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}`}>
          {message}
        </div>
      )}

      {/* AI Provider Selection */}
      <div className="card bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 border-2 border-purple-200 dark:border-purple-800">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-semibold text-purple-900 dark:text-purple-100">Provedor de IA para Cotacoes</h2>
            <p className="text-sm text-purple-700 dark:text-purple-300 mt-1">Selecione qual provedor de IA sera usado para analise de imagens e OCR nas cotacoes</p>
          </div>
        </div>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-4">
            {aiProviders.map((provider) => (
              <label
                key={provider.value}
                className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  selectedAIProvider === provider.value
                    ? 'border-purple-500 bg-purple-100 dark:bg-purple-900/40'
                    : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:border-purple-300 dark:hover:border-purple-500'
                }`}
              >
                <input
                  type="radio"
                  name="ai_provider"
                  value={provider.value}
                  checked={selectedAIProvider === provider.value}
                  onChange={(e) => setSelectedAIProvider(e.target.value)}
                  className="sr-only"
                />
                <div className="flex items-center">
                  {provider.value === 'anthropic' ? (
                    <svg className="w-8 h-8 mr-3 text-orange-600 dark:text-orange-400" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  ) : (
                    <svg className="w-8 h-8 mr-3 text-green-600 dark:text-green-400" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729z"/>
                    </svg>
                  )}
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100">{provider.label}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {provider.value === 'anthropic' ? 'Melhor para OCR complexo' : 'Rapido e versatil'}
                    </div>
                  </div>
                </div>
                {selectedAIProvider === provider.value && (
                  <svg className="w-5 h-5 ml-3 text-purple-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  </svg>
                )}
              </label>
            ))}
          </div>
          <button
            onClick={handleSaveAIProvider}
            className="btn-primary bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={saving || !isAdmin}
            title={!isAdmin ? 'Apenas administradores podem alterar esta configuracao' : ''}
          >
            {saving ? 'Salvando...' : 'Salvar Provedor'}
          </button>
        </div>
      </div>

      {/* Taxa de Cambio USD/BRL - Banco Central (BCB PTAX) */}
      <div className="card bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-2 border-green-200 dark:border-green-800">
        {renderIntegrationMessage('EXCHANGE')}
        {renderIntegrationMessage('BCB')}
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-semibold text-green-900 dark:text-green-100">Taxa de Cambio USD - BRL</h2>
            <p className="text-sm text-green-700 dark:text-green-300 mt-1">
              Cotacao PTAX do Banco Central do Brasil - Atualizacao automatica diaria as 23h
            </p>
          </div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
            {exchangeRateConfig?.source === 'BCB_PTAX' ? 'BCB PTAX' : exchangeRateConfig?.source || 'Nao configurado'}
          </span>
        </div>

        {/* Taxa atual (somente leitura) */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Cotacao atual</p>
              <p className="text-3xl font-bold text-green-700 dark:text-green-300">
                {exchangeRateConfig?.rate ? `R$ ${exchangeRateConfig.rate.toFixed(4)}` : 'R$ 6.00'}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                1 USD = {exchangeRateConfig?.rate?.toFixed(4) || '6.00'} BRL
              </p>
            </div>
            <div className="text-right">
              {exchangeRateConfig?.updated_at && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Atualizado em: {new Date(exchangeRateConfig.updated_at).toLocaleString('pt-BR')}
                </p>
              )}
              {exchangeRateConfig?.bcb_date && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Data BCB: {exchangeRateConfig.bcb_date}
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleUpdateExchangeRate}
            className="btn-primary bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            disabled={updatingExchangeRate || !isAdmin}
            title={!isAdmin ? 'Apenas administradores podem atualizar' : 'Buscar cotacao mais recente do BCB'}
          >
            {updatingExchangeRate ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Atualizando...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Atualizar Agora
              </>
            )}
          </button>
          <button
            onClick={handleTestBCB}
            className="btn-secondary"
            disabled={testingBCB}
          >
            {testingBCB ? 'Testando...' : 'Testar Conexao BCB'}
          </button>
        </div>
      </div>

      {/* SerpAPI */}
      <div className="card">
        {renderIntegrationMessage('SERPAPI')}
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">SerpAPI</h2>
          {renderStatusBadge(serpApiStatus)}
        </div>
        {serpApiStatus?.is_configured && (
          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              <span className="font-medium">Chave atual:</span> {serpApiStatus.api_key_masked}
            </p>
          </div>
        )}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {serpApiStatus?.is_configured ? 'Nova API Key (deixe em branco para manter a atual)' : 'API Key'}
            </label>
            <input
              type="password"
              value={serpApiKey}
              onChange={(e) => setSerpApiKey(e.target.value)}
              className="input-field w-full"
              placeholder="Insira a chave da API SerpAPI"
            />
          </div>
          <div className="flex space-x-4">
            <button
              onClick={() => handleSave('SERPAPI', serpApiKey)}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={saving || !serpApiKey || !isAdmin}
            >
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
            <button
              onClick={() => handleTest('SERPAPI')}
              className="btn-secondary"
              disabled={testing === 'SERPAPI' || !serpApiStatus?.is_configured}
            >
              {testing === 'SERPAPI' ? 'Testando...' : 'Testar Conexao'}
            </button>
          </div>

          {/* Custo por chamada SerpAPI */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Custo por Chamada (R$)
            </label>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="0.0001"
                value={serpApiCostPerCall}
                onChange={(e) => setSerpApiCostPerCall(e.target.value)}
                className="input-field w-48"
                placeholder="Ex: 0.0125"
              />
              <button
                onClick={handleSaveSerpApiCost}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={saving || !serpApiCostPerCall || !isAdmin}
              >
                {saving ? 'Salvando...' : 'Salvar Custo'}
              </button>
            </div>
            {serpApiCostConfig?.cost_per_call && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                Custo atual: R$ {serpApiCostConfig.cost_per_call.toFixed(4)}/chamada
                {serpApiCostConfig.updated_at && (
                  <span className="ml-2">
                    (atualizado em {new Date(serpApiCostConfig.updated_at).toLocaleDateString('pt-BR')})
                  </span>
                )}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* imgbb */}
      <div className="card">
        {renderIntegrationMessage('IMGBB')}
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">imgbb</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Hospedagem de imagens para Google Lens
            </p>
          </div>
          {renderStatusBadge(imgbbStatus)}
        </div>
        {imgbbStatus?.is_configured && (
          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              <span className="font-medium">Chave atual:</span> {imgbbStatus.api_key_masked}
            </p>
          </div>
        )}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {imgbbStatus?.is_configured ? 'Nova API Key (deixe em branco para manter a atual)' : 'API Key'}
            </label>
            <input
              type="password"
              value={imgbbApiKey}
              onChange={(e) => setImgbbApiKey(e.target.value)}
              className="input-field w-full"
              placeholder="Insira a chave da API imgbb"
            />
          </div>
          <div className="flex space-x-4">
            <button
              onClick={() => handleSave('IMGBB', imgbbApiKey)}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={saving || !imgbbApiKey || !isAdmin}
            >
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
            <button
              onClick={() => handleTest('IMGBB')}
              className="btn-secondary"
              disabled={testing === 'IMGBB' || !imgbbStatus?.is_configured}
            >
              {testing === 'IMGBB' ? 'Testando...' : 'Testar Conexao'}
            </button>
          </div>
        </div>
      </div>

      {/* Anthropic (Claude) */}
      <div className={`card ${selectedAIProvider === 'anthropic' ? 'ring-2 ring-purple-500' : ''}`}>
        {renderIntegrationMessage('ANTHROPIC')}
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Anthropic (Claude)</h2>
            {selectedAIProvider === 'anthropic' && (
              <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 rounded-full">
                Ativo
              </span>
            )}
          </div>
          {renderStatusBadge(anthropicStatus)}
        </div>
        {anthropicStatus?.is_configured && (
          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg space-y-1">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              <span className="font-medium">Chave atual:</span> {anthropicStatus.api_key_masked}
            </p>
            {anthropicStatus.other_settings?.model && (
              <p className="text-sm text-gray-600 dark:text-gray-300">
                <span className="font-medium">Modelo atual:</span> {anthropicModels.find(m => m.value === anthropicStatus.other_settings?.model)?.label || anthropicStatus.other_settings.model}
              </p>
            )}
          </div>
        )}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {anthropicStatus?.is_configured ? 'Nova API Key (deixe em branco para manter a atual)' : 'API Key'}
            </label>
            <input
              type="password"
              value={anthropicApiKey}
              onChange={(e) => setAnthropicApiKey(e.target.value)}
              className="input-field w-full"
              placeholder="Insira a chave da API Anthropic"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Modelo Claude
            </label>
            <select
              value={selectedAnthropicModel}
              onChange={(e) => setSelectedAnthropicModel(e.target.value)}
              className="input-field w-full"
            >
              {anthropicModels.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex space-x-4">
            <button
              onClick={() => handleSaveAnthropic()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={saving || (!anthropicApiKey && selectedAnthropicModel === (anthropicStatus?.other_settings?.model || '')) || !isAdmin}
            >
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
            <button
              onClick={() => handleTest('ANTHROPIC')}
              className="btn-secondary"
              disabled={testing === 'ANTHROPIC' || !anthropicStatus?.is_configured}
            >
              {testing === 'ANTHROPIC' ? 'Testando...' : 'Testar Conexao'}
            </button>
          </div>
        </div>
      </div>

      {/* OpenAI (GPT) */}
      <div className={`card ${selectedAIProvider === 'openai' ? 'ring-2 ring-purple-500' : ''}`}>
        {renderIntegrationMessage('OPENAI')}
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">OpenAI (GPT)</h2>
            {selectedAIProvider === 'openai' && (
              <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 rounded-full">
                Ativo
              </span>
            )}
          </div>
          {renderStatusBadge(openaiStatus)}
        </div>
        {openaiStatus?.is_configured && (
          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg space-y-1">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              <span className="font-medium">Chave atual:</span> {openaiStatus.api_key_masked}
            </p>
            {openaiStatus.other_settings?.model && (
              <p className="text-sm text-gray-600 dark:text-gray-300">
                <span className="font-medium">Modelo atual:</span> {openaiModels.find(m => m.value === openaiStatus.other_settings?.model)?.label || openaiStatus.other_settings.model}
              </p>
            )}
          </div>
        )}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {openaiStatus?.is_configured ? 'Nova API Key (deixe em branco para manter a atual)' : 'API Key'}
            </label>
            <input
              type="password"
              value={openaiApiKey}
              onChange={(e) => setOpenaiApiKey(e.target.value)}
              className="input-field w-full"
              placeholder="Insira a chave da API OpenAI"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Modelo GPT
            </label>
            <select
              value={selectedOpenaiModel}
              onChange={(e) => setSelectedOpenaiModel(e.target.value)}
              className="input-field w-full"
            >
              {openaiModels.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex space-x-4">
            <button
              onClick={() => handleSaveOpenAI()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={saving || (!openaiApiKey && selectedOpenaiModel === (openaiStatus?.other_settings?.model || '')) || !isAdmin}
            >
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
            <button
              onClick={() => handleTest('OPENAI')}
              className="btn-secondary"
              disabled={testing === 'OPENAI' || !openaiStatus?.is_configured}
            >
              {testing === 'OPENAI' ? 'Testando...' : 'Testar Conexao'}
            </button>
          </div>
        </div>
      </div>

      {/* API FIPE */}
      <div className="card">
        {renderIntegrationMessage('FIPE')}
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">API FIPE</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Tabela FIPE para consulta de precos de veiculos
            </p>
          </div>
          {fipeStatus?.is_configured ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
              Configurado ({fipeStatus.other_settings?.api_type === 'private' ? 'API Privada' : 'API Publica'})
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
              Nao configurado
            </span>
          )}
        </div>

        <div className="space-y-4">
          {/* Tipo de API */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Tipo de API
            </label>
            <div className="flex gap-4">
              <label className={`flex items-center p-3 rounded-lg border-2 cursor-pointer transition-all ${
                fipeApiType === 'public'
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:border-blue-300'
              }`}>
                <input
                  type="radio"
                  name="fipe_api_type"
                  value="public"
                  checked={fipeApiType === 'public'}
                  onChange={() => setFipeApiType('public')}
                  className="sr-only"
                />
                <div>
                  <div className="font-medium text-gray-900 dark:text-gray-100">API Publica</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">Gratuita, sem necessidade de chave</div>
                </div>
                {fipeApiType === 'public' && (
                  <svg className="w-5 h-5 ml-2 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  </svg>
                )}
              </label>

              <label className={`flex items-center p-3 rounded-lg border-2 cursor-pointer transition-all ${
                fipeApiType === 'private'
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:border-blue-300'
              }`}>
                <input
                  type="radio"
                  name="fipe_api_type"
                  value="private"
                  checked={fipeApiType === 'private'}
                  onChange={() => setFipeApiType('private')}
                  className="sr-only"
                />
                <div>
                  <div className="font-medium text-gray-900 dark:text-gray-100">API Privada</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">Requer chave de acesso</div>
                </div>
                {fipeApiType === 'private' && (
                  <svg className="w-5 h-5 ml-2 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  </svg>
                )}
              </label>
            </div>
          </div>

          {/* Campo de API Key (apenas para API privada) */}
          {fipeApiType === 'private' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {fipeStatus?.is_configured && fipeStatus.other_settings?.api_type === 'private'
                  ? 'Nova API Key (deixe em branco para manter a atual)'
                  : 'API Key'}
              </label>
              <input
                type="password"
                value={fipeApiKey}
                onChange={(e) => setFipeApiKey(e.target.value)}
                className="input-field w-full"
                placeholder="Insira a chave da API FIPE privada"
              />
              {fipeStatus?.is_configured && fipeStatus.other_settings?.api_type === 'private' && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Chave atual: {fipeStatus.api_key_masked}
                </p>
              )}
            </div>
          )}

          <div className="flex space-x-4">
            <button
              onClick={handleSaveFipe}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={saving || (fipeApiType === 'private' && !fipeApiKey && !fipeStatus?.is_configured) || !isAdmin}
            >
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
            <button
              onClick={() => handleTest('FIPE')}
              className="btn-secondary"
              disabled={testing === 'FIPE'}
            >
              {testing === 'FIPE' ? 'Testando...' : 'Testar Conexao'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-6">Integracoes</h1>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('apis')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'apis'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
            }`}
          >
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              APIs Externas
            </div>
          </button>
          <button
            onClick={() => setActiveTab('middleware')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'middleware'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
            }`}
          >
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              Middleware (Apps)
            </div>
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'apis' ? renderApisTab() : renderMiddlewareTab()}
    </div>
  )
}
