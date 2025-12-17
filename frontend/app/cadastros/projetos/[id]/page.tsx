'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import AdminRoute from '@/components/AdminRoute'

interface Client {
  id: number
  nome: string
  nome_curto: string | null
}

interface Project {
  id: number
  client_id: number
  client: Client | null
  nome: string
  codigo: string | null
  descricao: string | null
  numero_contrato: string | null
  status: string
  created_at: string
  total_cotacoes: number
}

interface BankPriceItem {
  id?: number
  codigo: string
  material: string
  caracteristicas: string
  vl_mercado: number | null
  update_mode: string
}

interface ConfigVersion {
  id: number
  project_id: number
  versao: number
  descricao_alteracao: string | null
  criado_por: string | null
  ativo: boolean
  created_at: string
  // Parâmetros de cotação
  numero_cotacoes_por_pesquisa: number | null
  variacao_maxima_percent: number | null
  pesquisador_padrao: string | null
  local_padrao: string | null
  // Parâmetros de busca
  serpapi_location: string | null
  serpapi_gl: string | null
  serpapi_hl: string | null
  serpapi_num_results: number | null
  search_timeout: number | null
  max_sources: number | null
  // Fator de reavaliação
  ec_map: Record<string, number> | null
  pu_map: Record<string, number> | null
  vuf_map: Record<string, number> | null
  weights: Record<string, number> | null
  banco_precos: BankPriceItem[]
  total_cotacoes: number
  resumo_mudancas?: {
    tipo: string
    mensagem?: string
    total_mudancas?: number
    mudancas?: string[]
  }
}

interface Quote {
  id: number
  created_at: string
  status: string
  input_text: string | null
  codigo_item: string | null
  nome_item: string | null
  search_query_final: string | null
  valor_medio: number | null
  valor_minimo: number | null
  valor_maximo: number | null
  error_message: string | null
}

interface FinancialTransaction {
  date: string
  api: string
  quote_id: number
  client_name: string | null
  user_name: string | null
  description: string
  cost_usd: number
  cost_brl: number
}

interface FinancialIntegrationTotal {
  api: string
  total_usd: number
  total_brl: number
  transaction_count: number
}

interface FinancialReportData {
  total_usd: number
  total_brl: number
  totals_by_integration: FinancialIntegrationTotal[]
  transactions: FinancialTransaction[]
  period_start: string | null
  period_end: string | null
  usd_to_brl_rate: number
}

interface MonthOption {
  value: string
  label: string
}

interface IntegrationOption {
  value: string
  label: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type TabType = 'cotacoes' | 'parametros' | 'banco-precos' | 'fator-reavaliacao' | 'versoes' | 'financeiro'

// Helper para formatar valores monetários de forma segura
const formatCurrency = (value: number | string | null): string => {
  if (value === null || value === undefined) return '-'
  const numValue = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(numValue)) return '-'
  return `R$ ${numValue.toFixed(2)}`
}

const defaultEcMap = { 'OTIMO': 1.0, 'BOM': 0.8, 'REGULAR': 0.6, 'RUIM': 0.4 }
const defaultPuMap = { '0-2': 1.0, '2-5': 0.85, '5-10': 0.7, '>10': 0.5 }
const defaultVufMap = { '>5': 1.0, '3-5': 0.8, '1-3': 0.6, '<1': 0.4 }
const defaultWeights = { 'ec': 0.4, 'pu': 0.3, 'vuf': 0.3 }

export default function ProjectDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const { user } = useAuth()

  const [project, setProject] = useState<Project | null>(null)
  const [activeConfig, setActiveConfig] = useState<ConfigVersion | null>(null)
  const [versions, setVersions] = useState<ConfigVersion[]>([])
  const [quotes, setQuotes] = useState<Quote[]>([])

  // Financial state
  const [financialData, setFinancialData] = useState<FinancialReportData | null>(null)
  const [financialLoading, setFinancialLoading] = useState(false)
  const [financialHasSearched, setFinancialHasSearched] = useState(false)
  const [financialPeriodType, setFinancialPeriodType] = useState<string>('')
  const [financialStartDate, setFinancialStartDate] = useState('')
  const [financialEndDate, setFinancialEndDate] = useState('')
  const [financialMonthRef, setFinancialMonthRef] = useState('')
  const [financialSelectedIntegrations, setFinancialSelectedIntegrations] = useState<string[]>([])
  const [monthOptions, setMonthOptions] = useState<MonthOption[]>([])
  const [integrationOptions, setIntegrationOptions] = useState<IntegrationOption[]>([])

  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('cotacoes')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Form state para parâmetros
  const [paramForm, setParamForm] = useState({
    // Parâmetros de cotação
    numero_cotacoes_por_pesquisa: 3,
    variacao_maxima_percent: 25,
    pesquisador_padrao: user?.nome || '',
    local_padrao: '',
    // Parâmetros de busca
    serpapi_location: '',
    serpapi_gl: 'br',
    serpapi_hl: 'pt',
    serpapi_num_results: 10,
    search_timeout: 30,
    max_sources: 10,
  })

  // Form state para banco de preços
  const [bankPrices, setBankPrices] = useState<BankPriceItem[]>([])
  const [newBankItem, setNewBankItem] = useState<BankPriceItem>({
    codigo: '',
    material: '',
    caracteristicas: '',
    vl_mercado: null,
    update_mode: 'MARKET'
  })

  // Form state para fator de reavaliação
  const [ecMap, setEcMap] = useState<Record<string, number>>(defaultEcMap)
  const [puMap, setPuMap] = useState<Record<string, number>>(defaultPuMap)
  const [vufMap, setVufMap] = useState<Record<string, number>>(defaultVufMap)
  const [weights, setWeights] = useState<Record<string, number>>(defaultWeights)

  const fetchProject = async () => {
    try {
      const res = await fetch(`${API_URL}/api/projects/${projectId}`)
      if (!res.ok) throw new Error('Projeto não encontrado')
      const data = await res.json()
      setProject(data)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const fetchActiveConfig = async () => {
    try {
      const res = await fetch(`${API_URL}/api/projects/${projectId}/config/versions/active`)
      if (res.ok) {
        const data = await res.json()
        if (data) {
          setActiveConfig(data)
          // Preencher formulários com dados da config ativa
          setParamForm({
            // Parâmetros de cotação
            numero_cotacoes_por_pesquisa: data.numero_cotacoes_por_pesquisa || 3,
            variacao_maxima_percent: data.variacao_maxima_percent || 25,
            pesquisador_padrao: data.pesquisador_padrao || '',
            local_padrao: data.local_padrao || '',
            // Parâmetros de busca
            serpapi_location: data.serpapi_location || '',
            serpapi_gl: data.serpapi_gl || 'br',
            serpapi_hl: data.serpapi_hl || 'pt',
            serpapi_num_results: data.serpapi_num_results || 10,
            search_timeout: data.search_timeout || 30,
            max_sources: data.max_sources || 10,
          })
          setBankPrices(data.banco_precos || [])
          setEcMap(data.ec_map || defaultEcMap)
          setPuMap(data.pu_map || defaultPuMap)
          setVufMap(data.vuf_map || defaultVufMap)
          setWeights(data.weights || defaultWeights)
        }
      }
    } catch (err) {
      console.error('Erro ao carregar config ativa:', err)
    }
  }

  const fetchVersions = async () => {
    try {
      const res = await fetch(`${API_URL}/api/projects/${projectId}/config/versions`)
      if (res.ok) {
        const data = await res.json()
        setVersions(data.items || [])
      }
    } catch (err) {
      console.error('Erro ao carregar versões:', err)
    }
  }

  const fetchQuotes = async () => {
    try {
      const res = await fetch(`${API_URL}/api/quotes?project_id=${projectId}`)
      if (res.ok) {
        const data = await res.json()
        setQuotes(Array.isArray(data) ? data : data.items || [])
      }
    } catch (err) {
      console.error('Erro ao carregar cotações:', err)
    }
  }

  const loadFinancialOptions = async () => {
    if (user?.role !== 'ADMIN') return

    try {
      const [monthsRes, integrationsRes] = await Promise.all([
        fetch(`${API_URL}/api/v2/financial/months`),
        fetch(`${API_URL}/api/v2/financial/integrations`)
      ])

      if (monthsRes.ok) {
        const months = await monthsRes.json()
        setMonthOptions(months)
      }

      if (integrationsRes.ok) {
        const integrations = await integrationsRes.json()
        setIntegrationOptions(integrations)
      }
    } catch (err) {
      console.error('Erro ao carregar opções financeiras:', err)
    }
  }

  const fetchFinancialReport = async () => {
    if (user?.role !== 'ADMIN') return
    if (!financialPeriodType && financialSelectedIntegrations.length === 0) return

    setFinancialLoading(true)
    setFinancialHasSearched(true)

    try {
      const params = new URLSearchParams()

      if (financialPeriodType === '7d' || financialPeriodType === '15d' || financialPeriodType === '30d') {
        params.append('period', financialPeriodType)
      } else if (financialPeriodType === 'specific' && financialStartDate && financialEndDate) {
        params.append('period', 'specific')
        params.append('start_date', new Date(financialStartDate).toISOString())
        params.append('end_date', new Date(financialEndDate + 'T23:59:59').toISOString())
      } else if (financialPeriodType === 'month' && financialMonthRef) {
        params.append('period', 'month')
        params.append('month_ref', financialMonthRef)
      }

      if (financialSelectedIntegrations.length > 0) {
        params.append('integrations', financialSelectedIntegrations.join(','))
      }

      const res = await fetch(`${API_URL}/api/v2/financial/project/${projectId}/report?${params}`)
      if (res.ok) {
        const data = await res.json()
        setFinancialData(data)
      }
    } catch (err) {
      console.error('Erro ao carregar relatório financeiro:', err)
    } finally {
      setFinancialLoading(false)
    }
  }

  const handleFinancialIntegrationToggle = (value: string) => {
    setFinancialSelectedIntegrations(prev =>
      prev.includes(value)
        ? prev.filter(v => v !== value)
        : [...prev, value]
    )
  }

  const getApiColor = (api: string) => {
    switch (api) {
      case 'anthropic':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      case 'serpapi':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'openai':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  const getApiLabel = (api: string) => {
    switch (api) {
      case 'anthropic':
        return 'Anthropic'
      case 'serpapi':
        return 'SerpAPI'
      case 'openai':
        return 'OpenAI'
      default:
        return api.toUpperCase()
    }
  }

  const getFinancialPeriodLabel = () => {
    if (financialPeriodType === '7d') return 'Últimos 7 dias'
    if (financialPeriodType === '15d') return 'Últimos 15 dias'
    if (financialPeriodType === '30d') return 'Últimos 30 dias'
    if (financialPeriodType === 'specific' && financialStartDate && financialEndDate) {
      return `${new Date(financialStartDate).toLocaleDateString('pt-BR')} a ${new Date(financialEndDate).toLocaleDateString('pt-BR')}`
    }
    if (financialPeriodType === 'month' && financialMonthRef) {
      const opt = monthOptions.find(m => m.value === financialMonthRef)
      return opt?.label || financialMonthRef
    }
    return 'Todos'
  }

  const getFinancialIntegrationsLabel = () => {
    if (financialSelectedIntegrations.length === 0) return 'Todas'
    return financialSelectedIntegrations.map(i => getApiLabel(i)).join(', ')
  }

  const generateFinancialPDF = () => {
    if (!financialData || !project) return

    const printContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Extrato Financeiro - ${project.nome}</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { font-family: Arial, sans-serif; padding: 20px; font-size: 11px; }
          .header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #1e40af; }
          .logo { font-size: 24px; font-weight: bold; color: #1e40af; margin-bottom: 5px; }
          .subtitle { color: #666; font-size: 14px; }
          .project-name { font-size: 16px; color: #374151; margin-top: 10px; }
          .filters { background: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
          .filters h3 { font-size: 12px; color: #374151; margin-bottom: 10px; }
          .filters-grid { display: flex; gap: 30px; flex-wrap: wrap; }
          .filter-item { }
          .filter-label { font-weight: bold; color: #6b7280; font-size: 10px; }
          .filter-value { color: #111827; margin-top: 2px; }
          .totals { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
          .total-card { background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px; border-radius: 6px; min-width: 120px; }
          .total-label { font-size: 10px; color: #6b7280; }
          .total-value { font-size: 16px; font-weight: bold; color: #111827; }
          .total-usd { font-size: 11px; color: #6b7280; }
          table { width: 100%; border-collapse: collapse; margin-top: 10px; }
          th { background: #f3f4f6; padding: 8px 6px; text-align: left; font-size: 10px; color: #374151; border-bottom: 2px solid #d1d5db; }
          th.right { text-align: right; }
          td { padding: 8px 6px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
          td.right { text-align: right; }
          .api-badge { display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 9px; font-weight: 500; }
          .api-anthropic { background: #ffedd5; color: #9a3412; }
          .api-serpapi { background: #dcfce7; color: #166534; }
          .api-openai { background: #dbeafe; color: #1e40af; }
          .wrap-cell { max-width: 100px; word-wrap: break-word; }
          .desc-cell { max-width: 180px; word-wrap: break-word; font-size: 10px; }
          .cost-usd { font-size: 9px; color: #6b7280; }
          tfoot td { font-weight: bold; background: #f9fafb; border-top: 2px solid #d1d5db; }
          .footer { margin-top: 30px; text-align: center; font-size: 10px; color: #9ca3af; padding-top: 20px; border-top: 1px solid #e5e7eb; }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="logo">Reavaliação Patrimonial</div>
          <div class="subtitle">Extrato Financeiro do Projeto</div>
          <div class="project-name">${project.nome}</div>
        </div>

        <div class="filters">
          <h3>Filtros Aplicados</h3>
          <div class="filters-grid">
            <div class="filter-item">
              <div class="filter-label">Período</div>
              <div class="filter-value">${getFinancialPeriodLabel()}</div>
            </div>
            <div class="filter-item">
              <div class="filter-label">Integrações</div>
              <div class="filter-value">${getFinancialIntegrationsLabel()}</div>
            </div>
            <div class="filter-item">
              <div class="filter-label">Taxa de Câmbio</div>
              <div class="filter-value">R$ ${financialData.usd_to_brl_rate.toFixed(2)} / USD</div>
            </div>
            <div class="filter-item">
              <div class="filter-label">Data do Relatório</div>
              <div class="filter-value">${new Date().toLocaleString('pt-BR')}</div>
            </div>
          </div>
        </div>

        <div class="totals">
          <div class="total-card">
            <div class="total-label">Total Geral</div>
            <div class="total-value">R$ ${financialData.total_brl.toFixed(2)}</div>
            ${financialData.total_usd > 0 ? `<div class="total-usd">US$ ${financialData.total_usd.toFixed(2)}</div>` : ''}
          </div>
          ${financialData.totals_by_integration.map(t => `
            <div class="total-card">
              <div class="total-label">${getApiLabel(t.api)} (${t.transaction_count})</div>
              <div class="total-value">R$ ${t.total_brl.toFixed(2)}</div>
              ${t.total_usd > 0 ? `<div class="total-usd">US$ ${t.total_usd.toFixed(2)}</div>` : ''}
            </div>
          `).join('')}
        </div>

        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th>API</th>
              <th>Cot.</th>
              <th>Usuário</th>
              <th>Descrição</th>
              <th class="right">Valor (R$)</th>
            </tr>
          </thead>
          <tbody>
            ${financialData.transactions.map(tx => `
              <tr>
                <td>${new Date(tx.date).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })}</td>
                <td><span class="api-badge api-${tx.api}">${getApiLabel(tx.api)}</span></td>
                <td>#${tx.quote_id}</td>
                <td class="wrap-cell">${tx.user_name || '-'}</td>
                <td class="desc-cell">${tx.description}</td>
                <td class="right">
                  R$ ${tx.cost_brl.toFixed(2)}
                  ${tx.cost_usd > 0 ? `<div class="cost-usd">US$ ${tx.cost_usd.toFixed(2)}</div>` : ''}
                </td>
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr>
              <td colspan="5" class="right">TOTAL:</td>
              <td class="right">
                R$ ${financialData.total_brl.toFixed(2)}
                ${financialData.total_usd > 0 ? `<div class="cost-usd">US$ ${financialData.total_usd.toFixed(2)}</div>` : ''}
              </td>
            </tr>
          </tfoot>
        </table>

        <div class="footer">
          Sistema de Reavaliação Patrimonial - Extrato gerado em ${new Date().toLocaleString('pt-BR')}
        </div>
      </body>
      </html>
    `

    const printWindow = window.open('', '_blank')
    if (printWindow) {
      printWindow.document.write(printContent)
      printWindow.document.close()
      printWindow.focus()
      setTimeout(() => {
        printWindow.print()
      }, 250)
    }
  }

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([
        fetchProject(),
        fetchActiveConfig(),
        fetchVersions(),
        fetchQuotes(),
        ...(user?.role === 'ADMIN' ? [loadFinancialOptions()] : [])
      ])
      setLoading(false)
    }
    loadData()
  }, [projectId])

  const saveConfig = async (descricao?: string) => {
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const payload = {
        descricao_alteracao: descricao || 'Atualização de configurações',
        ...paramForm,
        banco_precos: bankPrices,
        ec_map: ecMap,
        pu_map: puMap,
        vuf_map: vufMap,
        weights: weights,
      }

      // SEMPRE criar nova versão (POST), nunca atualizar (PUT)
      const url = `${API_URL}/api/projects/${projectId}/config/versions`

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao salvar')
      }

      const newVersion = await res.json()
      setSuccess(`Nova versão ${newVersion.versao} criada com sucesso!`)
      await fetchActiveConfig()
      await fetchVersions()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const activateVersion = async (versionId: number) => {
    try {
      const res = await fetch(
        `${API_URL}/api/projects/${projectId}/config/versions/${versionId}/activate`,
        { method: 'POST' }
      )
      if (!res.ok) throw new Error('Erro ao ativar versão')
      await fetchActiveConfig()
      await fetchVersions()
      setSuccess('Versão ativada com sucesso!')
    } catch (err: any) {
      setError(err.message)
    }
  }

  const addBankItem = () => {
    if (!newBankItem.codigo || !newBankItem.material) {
      setError('Código e Material são obrigatórios')
      return
    }
    setBankPrices([...bankPrices, { ...newBankItem }])
    setNewBankItem({
      codigo: '',
      material: '',
      caracteristicas: '',
      vl_mercado: null,
      update_mode: 'MARKET'
    })
  }

  const removeBankItem = (index: number) => {
    setBankPrices(bankPrices.filter((_, i) => i !== index))
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      PLANEJAMENTO: 'bg-gray-100 text-gray-800',
      EM_ANDAMENTO: 'bg-blue-100 text-blue-800',
      CONCLUIDO: 'bg-green-100 text-green-800',
      CANCELADO: 'bg-red-100 text-red-800',
      SUSPENSO: 'bg-yellow-100 text-yellow-800',
    }
    return (
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>
        {status}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Carregando...</div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-300">Projeto não encontrado</h2>
        <Link href="/cadastros/projetos" className="text-primary-600 dark:text-primary-400 hover:underline mt-4 inline-block">
          Voltar para lista
        </Link>
      </div>
    )
  }

  return (
    <AdminRoute>
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 mb-4 sm:mb-6">
        <div className="flex-1 min-w-0">
          <Link href="/cadastros/projetos" className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 mb-1 sm:mb-2 inline-block">
            &larr; Voltar
          </Link>
          <h1 className="text-lg sm:text-2xl font-bold text-gray-900 dark:text-gray-100 truncate">{project.nome}</h1>
          <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-1">
            <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 truncate max-w-[150px] sm:max-w-none">{project.client?.nome || 'Sem cliente'}</span>
            {getStatusBadge(project.status)}
            {activeConfig && (
              <span className="text-xs sm:text-sm text-primary-600 dark:text-primary-400">
                v{activeConfig.versao}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={() => saveConfig()}
          disabled={saving}
          className="w-full sm:w-auto px-3 sm:px-4 py-1.5 sm:py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 whitespace-nowrap"
        >
          {saving ? 'Salvando...' : 'Salvar Config'}
        </button>
      </div>

      {/* Mensagens */}
      {error && (
        <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg">{error}</div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded-lg">{success}</div>
      )}

      {/* Tabs */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm">
        <div className="border-b dark:border-gray-700 overflow-x-auto">
          <nav className="flex min-w-max">
            {[
              { id: 'cotacoes', label: `Cotações`, shortLabel: `Cot. (${quotes.length})` },
              { id: 'parametros', label: 'Parâmetros', shortLabel: 'Parâm.' },
              { id: 'banco-precos', label: 'Banco de Preços', shortLabel: 'Preços' },
              { id: 'fator-reavaliacao', label: 'Fator Reavaliação', shortLabel: 'Fator' },
              { id: 'versoes', label: 'Versões', shortLabel: 'Versões' },
              ...(user?.role === 'ADMIN' ? [{ id: 'financeiro', label: 'Financeiro', shortLabel: 'Financ.' }] : []),
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`px-3 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                }`}
              >
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.shortLabel}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="p-3 sm:p-6">
          {/* Tab: Cotações */}
          {activeTab === 'cotacoes' && (
            <div className="space-y-4 sm:space-y-6">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 sm:gap-0">
                <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100">Cotações do Projeto</h3>
                <Link
                  href={`/cotacao?project_id=${projectId}`}
                  className="w-full sm:w-auto text-center px-3 sm:px-4 py-1.5 sm:py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                >
                  Nova Cotação
                </Link>
              </div>

              {quotes.length === 0 ? (
                <div className="text-center py-6 sm:py-8 text-sm text-gray-500 dark:text-gray-400">
                  Nenhuma cotação encontrada para este projeto
                </div>
              ) : (
                <>
                  {/* Desktop Table */}
                  <div className="hidden md:block overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                      <thead className="bg-gray-50 dark:bg-gray-900">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">ID</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Código</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Descrição</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Data</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Valor</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Ações</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {quotes.map((quote) => (
                          <tr key={quote.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-gray-100">
                              #{quote.id}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                              {quote.codigo_item || '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 max-w-[200px] truncate">
                              {quote.nome_item || quote.input_text?.substring(0, 50) || 'Sem descrição'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                              {new Date(quote.created_at).toLocaleDateString('pt-BR')}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {formatCurrency(quote.valor_medio)}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <span className={`px-2 py-1 text-xs rounded-full ${
                                quote.status === 'DONE'
                                  ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                                  : quote.status === 'PROCESSING'
                                  ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
                                  : quote.status === 'CANCELLED'
                                  ? 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                                  : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
                              }`}>
                                {quote.status === 'DONE' ? 'OK' : quote.status === 'PROCESSING' ? 'Proc.' : quote.status === 'CANCELLED' ? 'Canc.' : 'Erro'}
                              </span>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm">
                              <Link
                                href={`/cotacao/${quote.id}`}
                                className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 font-medium"
                              >
                                Ver
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile Cards */}
                  <div className="md:hidden space-y-2">
                    {quotes.map((quote) => (
                      <Link
                        key={quote.id}
                        href={`/cotacao/${quote.id}`}
                        className="block p-3 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600"
                      >
                        <div className="flex justify-between items-start mb-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">#{quote.id}</span>
                            {quote.codigo_item && (
                              <span className="text-xs text-gray-500 dark:text-gray-400">{quote.codigo_item}</span>
                            )}
                          </div>
                          <span className={`px-1.5 py-0.5 text-[10px] rounded-full ${
                            quote.status === 'DONE'
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                              : quote.status === 'PROCESSING'
                              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
                              : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
                          }`}>
                            {quote.status === 'DONE' ? 'OK' : quote.status === 'PROCESSING' ? 'Proc.' : 'Erro'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-300 truncate mb-1">
                          {quote.nome_item || quote.input_text?.substring(0, 40) || 'Sem descrição'}
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] text-gray-500 dark:text-gray-400">
                            {new Date(quote.created_at).toLocaleDateString('pt-BR')}
                          </span>
                          <span className="text-sm font-semibold text-primary-600 dark:text-primary-400">
                            {formatCurrency(quote.valor_medio)}
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Tab: Parâmetros */}
          {activeTab === 'parametros' && (
            <div className="space-y-6 sm:space-y-8">
              {/* Parâmetros de Cotação */}
              <div>
                <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-4">Parâmetros de Cotação</h3>
                <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mb-3 sm:mb-4">
                  Configure os parâmetros específicos para as cotações deste projeto.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Cotações por Pesquisa
                    </label>
                    <input
                      type="number"
                      value={paramForm.numero_cotacoes_por_pesquisa}
                      onChange={(e) => setParamForm({ ...paramForm, numero_cotacoes_por_pesquisa: Number(e.target.value) })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Variação Máxima (%)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={paramForm.variacao_maxima_percent}
                      onChange={(e) => setParamForm({ ...paramForm, variacao_maxima_percent: Number(e.target.value) })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Pesquisador Padrão
                    </label>
                    <input
                      type="text"
                      value={paramForm.pesquisador_padrao}
                      readOnly
                      placeholder="Ex: Sistema"
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-600 cursor-not-allowed text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Local Padrão
                    </label>
                    <input
                      type="text"
                      value={paramForm.local_padrao}
                      onChange={(e) => setParamForm({ ...paramForm, local_padrao: e.target.value })}
                      placeholder="Ex: Online"
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                </div>
              </div>

              {/* Parâmetros de Busca */}
              <div>
                <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-4">Parâmetros de Busca (SerpAPI)</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Localização
                    </label>
                    <input
                      type="text"
                      value={paramForm.serpapi_location}
                      onChange={(e) => setParamForm({ ...paramForm, serpapi_location: e.target.value })}
                      placeholder="Ex: São Paulo, Brazil"
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      País (gl)
                    </label>
                    <input
                      type="text"
                      value={paramForm.serpapi_gl}
                      onChange={(e) => setParamForm({ ...paramForm, serpapi_gl: e.target.value })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Idioma (hl)
                    </label>
                    <input
                      type="text"
                      value={paramForm.serpapi_hl}
                      onChange={(e) => setParamForm({ ...paramForm, serpapi_hl: e.target.value })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Nº Resultados
                    </label>
                    <input
                      type="number"
                      value={paramForm.serpapi_num_results}
                      onChange={(e) => setParamForm({ ...paramForm, serpapi_num_results: Number(e.target.value) })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Timeout (s)
                    </label>
                    <input
                      type="number"
                      value={paramForm.search_timeout}
                      onChange={(e) => setParamForm({ ...paramForm, search_timeout: Number(e.target.value) })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Máx. Fontes
                    </label>
                    <input
                      type="number"
                      value={paramForm.max_sources}
                      onChange={(e) => setParamForm({ ...paramForm, max_sources: Number(e.target.value) })}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Banco de Preços */}
          {activeTab === 'banco-precos' && (
            <div className="space-y-4 sm:space-y-6">
              <div>
                <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100">Banco de Preços do Projeto</h3>
                <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Defina preços de referência para materiais específicos.
                </p>
              </div>

              {/* Formulário para adicionar item */}
              <div className="bg-gray-50 dark:bg-gray-700 p-3 sm:p-4 rounded-lg">
                <h4 className="text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 sm:mb-3">Adicionar Item</h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
                  <input
                    type="text"
                    placeholder="Código"
                    value={newBankItem.codigo}
                    onChange={(e) => setNewBankItem({ ...newBankItem, codigo: e.target.value })}
                    className="px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs sm:text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <input
                    type="text"
                    placeholder="Material"
                    value={newBankItem.material}
                    onChange={(e) => setNewBankItem({ ...newBankItem, material: e.target.value })}
                    className="px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs sm:text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <input
                    type="text"
                    placeholder="Características"
                    value={newBankItem.caracteristicas}
                    onChange={(e) => setNewBankItem({ ...newBankItem, caracteristicas: e.target.value })}
                    className="px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs sm:text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 col-span-2 sm:col-span-1"
                  />
                  <input
                    type="number"
                    placeholder="Valor (R$)"
                    value={newBankItem.vl_mercado || ''}
                    onChange={(e) => setNewBankItem({ ...newBankItem, vl_mercado: e.target.value ? Number(e.target.value) : null })}
                    className="px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs sm:text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <button
                    onClick={addBankItem}
                    className="px-3 sm:px-4 py-1.5 sm:py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-xs sm:text-sm"
                  >
                    Adicionar
                  </button>
                </div>
              </div>

              {/* Lista de itens */}
              {bankPrices.length === 0 ? (
                <div className="text-center py-6 sm:py-8 text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                  Nenhum item no banco de preços
                </div>
              ) : (
                <>
                  {/* Desktop Table */}
                  <div className="hidden sm:block overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50 dark:bg-gray-900">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Código</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Material</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase hidden lg:table-cell">Caract.</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Valor</th>
                          <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Modo</th>
                          <th className="px-3 py-2"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y dark:divide-gray-700">
                        {bankPrices.map((item, index) => (
                          <tr key={index}>
                            <td className="px-3 py-2 text-xs sm:text-sm text-gray-900 dark:text-gray-100">{item.codigo}</td>
                            <td className="px-3 py-2 text-xs sm:text-sm text-gray-900 dark:text-gray-100 max-w-[150px] truncate">{item.material}</td>
                            <td className="px-3 py-2 text-xs sm:text-sm text-gray-500 dark:text-gray-400 hidden lg:table-cell max-w-[100px] truncate">{item.caracteristicas}</td>
                            <td className="px-3 py-2 text-xs sm:text-sm text-right text-gray-900 dark:text-gray-100">
                              {formatCurrency(item.vl_mercado)}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <select
                                value={item.update_mode}
                                onChange={(e) => {
                                  const updated = [...bankPrices]
                                  updated[index].update_mode = e.target.value
                                  setBankPrices(updated)
                                }}
                                className="text-xs border dark:border-gray-600 rounded px-1 py-0.5 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                              >
                                <option value="MARKET">Mercado</option>
                                <option value="IPCA">IPCA</option>
                                <option value="MANUAL">Manual</option>
                                <option value="SKIP">Ignorar</option>
                              </select>
                            </td>
                            <td className="px-3 py-2 text-right">
                              <button
                                onClick={() => removeBankItem(index)}
                                className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-xs"
                              >
                                Remover
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile Cards */}
                  <div className="sm:hidden space-y-2">
                    {bankPrices.map((item, index) => (
                      <div key={index} className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <span className="text-xs font-medium text-gray-900 dark:text-gray-100">{item.codigo}</span>
                            <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">{item.material}</span>
                          </div>
                          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{formatCurrency(item.vl_mercado)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <select
                            value={item.update_mode}
                            onChange={(e) => {
                              const updated = [...bankPrices]
                              updated[index].update_mode = e.target.value
                              setBankPrices(updated)
                            }}
                            className="text-[10px] border dark:border-gray-600 rounded px-1 py-0.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                          >
                            <option value="MARKET">Mercado</option>
                            <option value="IPCA">IPCA</option>
                            <option value="MANUAL">Manual</option>
                            <option value="SKIP">Ignorar</option>
                          </select>
                          <button
                            onClick={() => removeBankItem(index)}
                            className="text-red-600 dark:text-red-400 text-xs"
                          >
                            Remover
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Tab: Fator de Reavaliação */}
          {activeTab === 'fator-reavaliacao' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Configuração do Fator de Reavaliação</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Configure os fatores para cálculo do valor de reavaliação baseado em Estado de Conservação (EC),
                Período de Utilização (PU) e Vida Útil Futura (VUF).
              </p>

              <div className="grid grid-cols-2 gap-6">
                {/* Estado de Conservação */}
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-3">Estado de Conservação (EC)</h4>
                  <div className="space-y-2">
                    {Object.entries(ecMap).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-3">
                        <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{key}</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          max="1"
                          value={value}
                          onChange={(e) => setEcMap({ ...ecMap, [key]: Number(e.target.value) })}
                          className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Período de Utilização */}
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-3">Período de Utilização (PU)</h4>
                  <div className="space-y-2">
                    {Object.entries(puMap).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-3">
                        <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{key} anos</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          max="1"
                          value={value}
                          onChange={(e) => setPuMap({ ...puMap, [key]: Number(e.target.value) })}
                          className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Vida Útil Futura */}
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-3">Vida Útil Futura (VUF)</h4>
                  <div className="space-y-2">
                    {Object.entries(vufMap).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-3">
                        <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{key} anos</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          max="1"
                          value={value}
                          onChange={(e) => setVufMap({ ...vufMap, [key]: Number(e.target.value) })}
                          className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Pesos */}
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-3">Pesos dos Fatores</h4>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">A soma dos pesos deve ser 1.0</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="w-24 text-sm text-gray-600 dark:text-gray-400">EC</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        value={weights.ec}
                        onChange={(e) => setWeights({ ...weights, ec: Number(e.target.value) })}
                        className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                      />
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="w-24 text-sm text-gray-600 dark:text-gray-400">PU</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        value={weights.pu}
                        onChange={(e) => setWeights({ ...weights, pu: Number(e.target.value) })}
                        className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                      />
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="w-24 text-sm text-gray-600 dark:text-gray-400">VUF</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        value={weights.vuf}
                        onChange={(e) => setWeights({ ...weights, vuf: Number(e.target.value) })}
                        className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                      />
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                      Soma: {(weights.ec + weights.pu + weights.vuf).toFixed(1)}
                      {Math.abs(weights.ec + weights.pu + weights.vuf - 1) > 0.01 && (
                        <span className="text-red-500 dark:text-red-400 ml-2">(deve ser 1.0)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Histórico de Versões */}
          {activeTab === 'versoes' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Histórico de Versões</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Todas as versões de configuração deste projeto. Versões com cotações vinculadas não podem ser excluídas.
              </p>

              {versions.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  Nenhuma versão de configuração criada
                </div>
              ) : (
                <div className="space-y-3">
                  {versions.map((version) => (
                    <div
                      key={version.id}
                      className={`p-4 rounded-lg border ${
                        version.ativo ? 'border-primary-300 bg-primary-50 dark:bg-primary-900/20' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3">
                            <span className="font-semibold text-gray-900 dark:text-gray-100">Versão {version.versao}</span>
                            {version.ativo && (
                              <span className="px-2 py-0.5 bg-primary-600 text-white text-xs rounded-full">
                                Ativa
                              </span>
                            )}
                            {version.total_cotacoes > 0 && (
                              <span className="px-2 py-0.5 bg-gray-200 text-gray-700 text-xs rounded-full">
                                {version.total_cotacoes} cotações
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 mt-1">
                            {version.descricao_alteracao || 'Sem descrição'}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            Criado em {new Date(version.created_at).toLocaleString('pt-BR')}
                            {version.criado_por && ` por ${version.criado_por}`}
                          </p>

                          {/* Resumo de mudanças */}
                          {version.resumo_mudancas && version.resumo_mudancas.tipo === 'atualizacao' && (
                            <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                              <p className="text-xs font-medium text-blue-900 mb-2">
                                Alterações ({version.resumo_mudancas.total_mudancas || 0}):
                              </p>
                              {version.resumo_mudancas.mudancas && version.resumo_mudancas.mudancas.length > 0 && (
                                <ul className="text-xs text-blue-800 space-y-1">
                                  {version.resumo_mudancas.mudancas.map((mudanca, idx) => (
                                    <li key={idx} className="flex items-start">
                                      <span className="mr-2">•</span>
                                      <span>{mudanca}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                          {version.resumo_mudancas && version.resumo_mudancas.tipo === 'criacao' && (
                            <div className="mt-3 p-3 bg-green-50 rounded-lg">
                              <p className="text-xs text-green-800">
                                {version.resumo_mudancas.mensagem}
                              </p>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2 ml-4">
                          {!version.ativo && (
                            <button
                              onClick={() => activateVersion(version.id)}
                              className="px-3 py-1 text-sm text-primary-600 hover:bg-primary-100 rounded"
                            >
                              Ativar
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab: Financeiro */}
          {activeTab === 'financeiro' && user?.role === 'ADMIN' && (
            <div className="space-y-4 sm:space-y-6">
              <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100">Extrato Financeiro do Projeto</h3>

              {/* Filtros */}
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 sm:p-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-3 sm:mb-4">
                  {/* Período */}
                  <div>
                    <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Período</label>
                    <select
                      value={financialPeriodType}
                      onChange={(e) => {
                        setFinancialPeriodType(e.target.value)
                        setFinancialStartDate('')
                        setFinancialEndDate('')
                        setFinancialMonthRef('')
                      }}
                      className="w-full px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-xs sm:text-sm"
                    >
                      <option value="">Selecione...</option>
                      <option value="7d">Últimos 7 dias</option>
                      <option value="15d">Últimos 15 dias</option>
                      <option value="30d">Últimos 30 dias</option>
                      <option value="specific">Datas Específicas</option>
                      <option value="month">Mês de Referência</option>
                    </select>
                  </div>

                  {financialPeriodType === 'specific' && (
                    <>
                      <div>
                        <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Data Início</label>
                        <input
                          type="date"
                          value={financialStartDate}
                          onChange={(e) => setFinancialStartDate(e.target.value)}
                          className="w-full px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-xs sm:text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Data Fim</label>
                        <input
                          type="date"
                          value={financialEndDate}
                          onChange={(e) => setFinancialEndDate(e.target.value)}
                          className="w-full px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-xs sm:text-sm"
                        />
                      </div>
                    </>
                  )}

                  {financialPeriodType === 'month' && (
                    <div>
                      <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mês de Referência</label>
                      <select
                        value={financialMonthRef}
                        onChange={(e) => setFinancialMonthRef(e.target.value)}
                        className="w-full px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-xs sm:text-sm"
                      >
                        <option value="">Selecione...</option>
                        {monthOptions.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {/* Integrações */}
                <div className="mb-3 sm:mb-4">
                  <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 sm:mb-2">Integrações</label>
                  <div className="flex flex-wrap gap-2">
                    {integrationOptions.map((opt) => (
                      <label
                        key={opt.value}
                        className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg border cursor-pointer text-xs sm:text-sm transition-colors ${
                          financialSelectedIntegrations.includes(opt.value)
                            ? 'bg-primary-100 dark:bg-primary-900/30 border-primary-500 text-primary-700 dark:text-primary-300'
                            : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={financialSelectedIntegrations.includes(opt.value)}
                          onChange={() => handleFinancialIntegrationToggle(opt.value)}
                          className="sr-only"
                        />
                        <span className={`w-2 h-2 rounded-full ${
                          opt.value === 'anthropic' ? 'bg-orange-500' :
                          opt.value === 'serpapi' ? 'bg-green-500' : 'bg-blue-500'
                        }`}></span>
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={fetchFinancialReport}
                    disabled={financialLoading || (!financialPeriodType && financialSelectedIntegrations.length === 0)}
                    className="px-3 sm:px-4 py-1.5 sm:py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-xs sm:text-sm flex items-center gap-2"
                  >
                    {financialLoading ? (
                      <>
                        <svg className="animate-spin h-3 w-3 sm:h-4 sm:w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Carregando...
                      </>
                    ) : 'Exibir'}
                  </button>
                </div>
              </div>

              {/* Resultados */}
              {financialHasSearched && financialData && (
                <>
                  {/* Totais */}
                  <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-3 sm:p-4">
                    {/* Total Geral */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b dark:border-gray-700 pb-3 mb-3 gap-2 sm:gap-0">
                      <div>
                        <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">Total Geral</p>
                        <div className="flex items-baseline gap-2 mt-1">
                          <span className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                            R$ {financialData.total_brl.toFixed(2)}
                          </span>
                          {financialData.total_usd > 0 && (
                            <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                              (US$ {financialData.total_usd.toFixed(2)})
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="sm:text-right text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                        Taxa: R$ {financialData.usd_to_brl_rate.toFixed(2)} / USD
                      </div>
                    </div>

                    {/* Totais por Integração */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
                      {financialData.totals_by_integration.map((total) => (
                        <div key={total.api} className="p-2 sm:p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`px-1.5 sm:px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-medium ${getApiColor(total.api)}`}>
                              {getApiLabel(total.api)}
                            </span>
                            <span className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">({total.transaction_count})</span>
                          </div>
                          <div className="flex items-baseline gap-1">
                            <span className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">
                              R$ {total.total_brl.toFixed(2)}
                            </span>
                            {total.total_usd > 0 && (
                              <span className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">
                                (US$ {total.total_usd.toFixed(2)})
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Extrato */}
                  <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg overflow-hidden">
                    {/* Header com botão PDF */}
                    <div className="p-3 sm:p-4 border-b dark:border-gray-700 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 sm:gap-0">
                      <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                        {financialData.transactions.length} transações
                        {financialData.period_start && financialData.period_end && (
                          <> | {new Date(financialData.period_start).toLocaleDateString('pt-BR')} a {new Date(financialData.period_end).toLocaleDateString('pt-BR')}</>
                        )}
                      </p>
                      {financialData.transactions.length > 0 && (
                        <button
                          onClick={generateFinancialPDF}
                          className="flex items-center justify-center gap-2 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-xs sm:text-sm"
                        >
                          <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                          </svg>
                          <span className="hidden sm:inline">Gerar PDF</span>
                          <span className="sm:hidden">PDF</span>
                        </button>
                      )}
                    </div>

                    {financialData.transactions.length === 0 ? (
                      <div className="p-6 sm:p-8 text-center text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                        Nenhuma transação encontrada para os filtros selecionados.
                      </div>
                    ) : (
                      <>
                        {/* Desktop Table */}
                        <div className="hidden md:block overflow-x-auto">
                          <table className="w-full">
                            <thead className="bg-gray-50 dark:bg-gray-900">
                              <tr>
                                <th className="text-left py-3 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-28">Data</th>
                                <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-20">API</th>
                                <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-14">Cot.</th>
                                <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-24">Usuário</th>
                                <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Descrição</th>
                                <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-24">Valor (R$)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                              {financialData.transactions.map((tx, idx) => (
                                <tr key={`${tx.quote_id}-${tx.api}-${idx}`} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                                  <td className="py-3 px-3 text-sm text-gray-900 dark:text-gray-100 whitespace-nowrap">
                                    {new Date(tx.date).toLocaleString('pt-BR', {
                                      day: '2-digit', month: '2-digit', year: '2-digit',
                                      hour: '2-digit', minute: '2-digit'
                                    })}
                                  </td>
                                  <td className="py-3 px-2">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getApiColor(tx.api)}`}>
                                      {getApiLabel(tx.api)}
                                    </span>
                                  </td>
                                  <td className="py-3 px-2 text-sm">
                                    <Link
                                      href={`/cotacao/${tx.quote_id}`}
                                      className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300"
                                    >
                                      #{tx.quote_id}
                                    </Link>
                                  </td>
                                  <td className="py-3 px-2 text-sm text-gray-500 dark:text-gray-400 break-words max-w-[96px]">
                                    {tx.user_name || '-'}
                                  </td>
                                  <td className="py-3 px-2 text-sm text-gray-500 dark:text-gray-400 break-words">
                                    {tx.description}
                                  </td>
                                  <td className="py-3 px-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                                    R$ {tx.cost_brl.toFixed(2)}
                                    {tx.cost_usd > 0 && (
                                      <span className="block text-xs text-gray-500 dark:text-gray-400">
                                        US$ {tx.cost_usd.toFixed(2)}
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot className="bg-gray-50 dark:bg-gray-900">
                              <tr>
                                <td colSpan={5} className="py-3 px-3 text-sm font-bold text-gray-900 dark:text-gray-100 text-right">
                                  TOTAL:
                                </td>
                                <td className="py-3 px-3 text-sm font-bold text-gray-900 dark:text-gray-100 text-right">
                                  R$ {financialData.total_brl.toFixed(2)}
                                  {financialData.total_usd > 0 && (
                                    <span className="block text-xs text-gray-500 dark:text-gray-400 font-normal">
                                      US$ {financialData.total_usd.toFixed(2)}
                                    </span>
                                  )}
                                </td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>

                        {/* Mobile Cards */}
                        <div className="md:hidden divide-y divide-gray-200 dark:divide-gray-700">
                          {financialData.transactions.map((tx, idx) => (
                            <Link
                              key={`${tx.quote_id}-${tx.api}-${idx}`}
                              href={`/cotacao/${tx.quote_id}`}
                              className="block p-3 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                            >
                              <div className="flex justify-between items-start mb-2">
                                <div className="flex items-center gap-2">
                                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${getApiColor(tx.api)}`}>
                                    {getApiLabel(tx.api)}
                                  </span>
                                  <span className="text-xs text-gray-500 dark:text-gray-400">#{tx.quote_id}</span>
                                </div>
                                <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                                  R$ {tx.cost_brl.toFixed(2)}
                                </span>
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 truncate">
                                {tx.description}
                              </div>
                              <div className="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500">
                                <span>
                                  {new Date(tx.date).toLocaleString('pt-BR', {
                                    day: '2-digit', month: '2-digit', year: '2-digit',
                                    hour: '2-digit', minute: '2-digit'
                                  })}
                                </span>
                                <span>{tx.user_name || '-'}</span>
                              </div>
                            </Link>
                          ))}
                          {/* Mobile Total */}
                          <div className="p-3 bg-gray-50 dark:bg-gray-900">
                            <div className="flex justify-between items-center">
                              <span className="text-xs sm:text-sm font-bold text-gray-900 dark:text-gray-100">TOTAL:</span>
                              <span className="text-sm sm:text-base font-bold text-gray-900 dark:text-gray-100">
                                R$ {financialData.total_brl.toFixed(2)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </>
              )}

              {/* Mensagem inicial */}
              {!financialHasSearched && (
                <div className="text-center py-8 sm:py-12 text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 rounded-lg">
                  <svg className="w-10 h-10 sm:w-12 sm:h-12 mx-auto mb-3 sm:mb-4 text-gray-300 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <p className="text-sm sm:text-base mb-1">Selecione os filtros</p>
                  <p className="text-xs sm:text-sm">Escolha um período e/ou integrações e clique em &quot;Exibir&quot;</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
    </AdminRoute>
  )
}
