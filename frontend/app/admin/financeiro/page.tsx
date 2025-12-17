'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import AdminRoute from '@/components/AdminRoute'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface TransactionItem {
  date: string
  api: string
  quote_id: number
  client_name: string | null
  project_name: string | null
  user_name: string | null
  description: string
  cost_usd: number
  cost_brl: number
}

interface IntegrationTotal {
  api: string
  total_usd: number
  total_brl: number
  transaction_count: number
}

interface ReportData {
  total_usd: number
  total_brl: number
  totals_by_integration: IntegrationTotal[]
  transactions: TransactionItem[]
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

type PeriodType = '7d' | '15d' | '30d' | 'specific' | 'month' | ''

export default function FinanceiroPage() {
  const { user } = useAuth()

  // Estado do relatório
  const [reportData, setReportData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  // Filtros
  const [periodType, setPeriodType] = useState<PeriodType>('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [monthRef, setMonthRef] = useState('')
  const [selectedIntegrations, setSelectedIntegrations] = useState<string[]>([])

  // Opções
  const [monthOptions, setMonthOptions] = useState<MonthOption[]>([])
  const [integrationOptions, setIntegrationOptions] = useState<IntegrationOption[]>([])


  // Carregar opções ao montar
  useEffect(() => {
    const loadOptions = async () => {
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
        console.error('Erro ao carregar opções:', err)
      }
    }

    loadOptions()
  }, [])

  const handleSearch = useCallback(async () => {
    // Validar que pelo menos um filtro foi selecionado
    if (!periodType && selectedIntegrations.length === 0) {
      return
    }

    setLoading(true)
    setHasSearched(true)

    try {
      const params = new URLSearchParams()

      // Período
      if (periodType === '7d' || periodType === '15d' || periodType === '30d') {
        params.append('period', periodType)
      } else if (periodType === 'specific' && startDate && endDate) {
        params.append('period', 'specific')
        params.append('start_date', new Date(startDate).toISOString())
        params.append('end_date', new Date(endDate + 'T23:59:59').toISOString())
      } else if (periodType === 'month' && monthRef) {
        params.append('period', 'month')
        params.append('month_ref', monthRef)
      }

      // Integrações
      if (selectedIntegrations.length > 0) {
        params.append('integrations', selectedIntegrations.join(','))
      }

      const res = await fetch(`${API_URL}/api/v2/financial/report?${params}`)
      const data = await res.json()
      setReportData(data)
    } catch (err) {
      console.error('Erro ao carregar relatório:', err)
    } finally {
      setLoading(false)
    }
  }, [periodType, startDate, endDate, monthRef, selectedIntegrations])

  const handleIntegrationToggle = (value: string) => {
    setSelectedIntegrations(prev =>
      prev.includes(value)
        ? prev.filter(v => v !== value)
        : [...prev, value]
    )
  }

  const formatCurrency = (value: number, currency: 'BRL' | 'USD' = 'BRL') => {
    if (currency === 'USD') {
      return `US$ ${value.toFixed(2)}`
    }
    return `R$ ${value.toFixed(2)}`
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
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

  const getPeriodLabel = () => {
    if (periodType === '7d') return 'Últimos 7 dias'
    if (periodType === '15d') return 'Últimos 15 dias'
    if (periodType === '30d') return 'Últimos 30 dias'
    if (periodType === 'specific' && startDate && endDate) {
      return `${new Date(startDate).toLocaleDateString('pt-BR')} a ${new Date(endDate).toLocaleDateString('pt-BR')}`
    }
    if (periodType === 'month' && monthRef) {
      const opt = monthOptions.find(m => m.value === monthRef)
      return opt?.label || monthRef
    }
    return 'Todos'
  }

  const getIntegrationsLabel = () => {
    if (selectedIntegrations.length === 0) return 'Todas'
    return selectedIntegrations.map(i => getApiLabel(i)).join(', ')
  }

  const generatePDF = async () => {
    if (!reportData) return

    // Criar conteúdo HTML para o PDF
    const printContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Extrato Financeiro - Reavaliação Patrimonial</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { font-family: Arial, sans-serif; padding: 20px; font-size: 11px; }
          .header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #1e40af; }
          .logo { font-size: 24px; font-weight: bold; color: #1e40af; margin-bottom: 5px; }
          .subtitle { color: #666; font-size: 14px; }
          .filters { background: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
          .filters h3 { font-size: 12px; color: #374151; margin-bottom: 10px; }
          .filters-grid { display: flex; gap: 30px; }
          .filter-item { }
          .filter-label { font-weight: bold; color: #6b7280; font-size: 10px; }
          .filter-value { color: #111827; margin-top: 2px; }
          .totals { display: flex; gap: 20px; margin-bottom: 20px; }
          .total-card { background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px; border-radius: 6px; flex: 1; }
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
          .desc-cell { max-width: 150px; word-wrap: break-word; font-size: 10px; }
          .cost-usd { font-size: 9px; color: #6b7280; }
          tfoot td { font-weight: bold; background: #f9fafb; border-top: 2px solid #d1d5db; }
          .footer { margin-top: 30px; text-align: center; font-size: 10px; color: #9ca3af; padding-top: 20px; border-top: 1px solid #e5e7eb; }
          @media print {
            body { padding: 10px; }
            .header { margin-bottom: 20px; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="logo">Reavaliação Patrimonial</div>
          <div class="subtitle">Extrato Financeiro</div>
        </div>

        <div class="filters">
          <h3>Filtros Aplicados</h3>
          <div class="filters-grid">
            <div class="filter-item">
              <div class="filter-label">Período</div>
              <div class="filter-value">${getPeriodLabel()}</div>
            </div>
            <div class="filter-item">
              <div class="filter-label">Integrações</div>
              <div class="filter-value">${getIntegrationsLabel()}</div>
            </div>
            <div class="filter-item">
              <div class="filter-label">Taxa de Câmbio</div>
              <div class="filter-value">R$ ${reportData.usd_to_brl_rate.toFixed(2)} / USD</div>
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
            <div class="total-value">R$ ${reportData.total_brl.toFixed(2)}</div>
            ${reportData.total_usd > 0 ? `<div class="total-usd">US$ ${reportData.total_usd.toFixed(2)}</div>` : ''}
          </div>
          ${reportData.totals_by_integration.map(t => `
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
              <th>Cliente</th>
              <th>Projeto</th>
              <th>Usuário</th>
              <th>Descrição</th>
              <th class="right">Valor (R$)</th>
            </tr>
          </thead>
          <tbody>
            ${reportData.transactions.map(tx => `
              <tr>
                <td>${new Date(tx.date).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })}</td>
                <td><span class="api-badge api-${tx.api}">${getApiLabel(tx.api)}</span></td>
                <td>#${tx.quote_id}</td>
                <td class="wrap-cell">${tx.client_name || '-'}</td>
                <td class="wrap-cell">${tx.project_name || '-'}</td>
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
              <td colspan="7" class="right">TOTAL:</td>
              <td class="right">
                R$ ${reportData.total_brl.toFixed(2)}
                ${reportData.total_usd > 0 ? `<div class="cost-usd">US$ ${reportData.total_usd.toFixed(2)}</div>` : ''}
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

    // Abrir nova janela para impressão/PDF
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

  if (user?.role !== 'ADMIN') {
    return (
      <div className="max-w-6xl">
        <h1 className="text-3xl font-bold mb-8 text-gray-900 dark:text-gray-100">Acesso Negado</h1>
        <p className="text-gray-600 dark:text-gray-400">Apenas administradores podem acessar esta página.</p>
      </div>
    )
  }

  return (
    <AdminRoute>
    <div className="max-w-7xl">
      <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold mb-4 sm:mb-8 text-gray-900 dark:text-gray-100">Financeiro</h1>

      {/* Filtros */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-4 sm:p-6 mb-4 sm:mb-6">
        <h2 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3 sm:mb-4">Filtros</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-6">
          {/* Período */}
          <div>
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 sm:mb-2">
              Período
            </label>
            <select
              value={periodType}
              onChange={(e) => {
                setPeriodType(e.target.value as PeriodType)
                setStartDate('')
                setEndDate('')
                setMonthRef('')
              }}
              className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              <option value="">Selecione...</option>
              <option value="7d">Últimos 7 dias</option>
              <option value="15d">Últimos 15 dias</option>
              <option value="30d">Últimos 30 dias</option>
              <option value="specific">Datas Específicas</option>
              <option value="month">Mês de Referência</option>
            </select>
          </div>

          {/* Datas Específicas */}
          {periodType === 'specific' && (
            <>
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 sm:mb-2">
                  Data Início
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 sm:mb-2">
                  Data Fim
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
            </>
          )}

          {/* Mês de Referência */}
          {periodType === 'month' && (
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 sm:mb-2">
                Mês de Referência
              </label>
              <select
                value={monthRef}
                onChange={(e) => setMonthRef(e.target.value)}
                className="w-full px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              >
                <option value="">Selecione...</option>
                {monthOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Integrações */}
          <div className="sm:col-span-2 lg:col-span-3">
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 sm:mb-2">
              Integrações
            </label>
            <div className="flex flex-wrap gap-2 sm:gap-3">
              {integrationOptions.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-lg border cursor-pointer transition-colors ${
                    selectedIntegrations.includes(opt.value)
                      ? 'bg-primary-100 border-primary-500 text-primary-700 dark:bg-primary-900 dark:border-primary-500 dark:text-primary-200'
                      : 'bg-white border-gray-300 text-gray-700 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedIntegrations.includes(opt.value)}
                    onChange={() => handleIntegrationToggle(opt.value)}
                    className="sr-only"
                  />
                  <span className={`w-2 h-2 sm:w-3 sm:h-3 rounded-full ${
                    opt.value === 'anthropic' ? 'bg-orange-500' :
                    opt.value === 'serpapi' ? 'bg-green-500' :
                    'bg-blue-500'
                  }`}></span>
                  {opt.label}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Botão Exibir */}
        <div className="mt-4 sm:mt-6 flex justify-end">
          <button
            onClick={handleSearch}
            disabled={loading || (!periodType && selectedIntegrations.length === 0)}
            className="px-4 sm:px-6 py-1.5 sm:py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Carregando...
              </>
            ) : (
              'Exibir'
            )}
          </button>
        </div>
      </div>

      {/* Resultados - apenas após busca */}
      {hasSearched && reportData && (
        <>
          {/* Totais */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-4 sm:p-6 mb-4 sm:mb-6">
            {/* Total Geral */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-gray-200 dark:border-gray-700 pb-3 sm:pb-4 mb-3 sm:mb-4 gap-2 sm:gap-0">
              <div>
                <h3 className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Total Geral</h3>
                <div className="flex items-baseline gap-2 sm:gap-3 mt-1">
                  <span className="text-xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">
                    {formatCurrency(reportData.total_brl)}
                  </span>
                  {reportData.total_usd > 0 && (
                    <span className="text-sm sm:text-lg text-gray-500 dark:text-gray-400">
                      ({formatCurrency(reportData.total_usd, 'USD')})
                    </span>
                  )}
                </div>
              </div>
              <div className="sm:text-right">
                <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                  Taxa: {formatCurrency(reportData.usd_to_brl_rate)} / USD
                </span>
              </div>
            </div>

            {/* Totais por Integração */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4">
              {reportData.totals_by_integration.map((total) => (
                <div
                  key={total.api}
                  className="p-3 sm:p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50"
                >
                  <div className="flex items-center gap-2 mb-1 sm:mb-2">
                    <span className={`px-1.5 sm:px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-medium ${getApiColor(total.api)}`}>
                      {getApiLabel(total.api)}
                    </span>
                    <span className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">
                      ({total.transaction_count} trans.)
                    </span>
                  </div>
                  <div className="flex items-baseline gap-1 sm:gap-2">
                    <span className="text-base sm:text-xl font-semibold text-gray-900 dark:text-gray-100">
                      {formatCurrency(total.total_brl)}
                    </span>
                    {total.total_usd > 0 && (
                      <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                        ({formatCurrency(total.total_usd, 'USD')})
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Extrato */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
            <div className="p-4 sm:p-6 border-b border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 sm:gap-0">
              <div>
                <h2 className="text-base sm:text-xl font-semibold text-gray-900 dark:text-gray-100">
                  Extrato Financeiro
                </h2>
                <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {reportData.transactions.length} transações
                  {reportData.period_start && reportData.period_end && (
                    <> | {new Date(reportData.period_start).toLocaleDateString('pt-BR')} a {new Date(reportData.period_end).toLocaleDateString('pt-BR')}</>
                  )}
                </p>
              </div>
              {reportData.transactions.length > 0 && (
                <button
                  onClick={generatePDF}
                  className="flex items-center justify-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                >
                  <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <span className="hidden sm:inline">Gerar PDF</span>
                  <span className="sm:hidden">PDF</span>
                </button>
              )}
            </div>

            {reportData.transactions.length === 0 ? (
              <div className="p-8 sm:p-12 text-center text-gray-500 dark:text-gray-400">
                Nenhuma transação encontrada para os filtros selecionados.
              </div>
            ) : (
              <>
                {/* Desktop Table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-900">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-32">
                          Data
                        </th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-20">
                          API
                        </th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-16">
                          Cot.
                        </th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-28">
                          Cliente
                        </th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-28">
                          Projeto
                        </th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">
                          Usuário
                        </th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-48">
                          Descrição
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">
                          Valor (R$)
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {reportData.transactions.map((tx, idx) => (
                        <tr key={`${tx.quote_id}-${tx.api}-${idx}`} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 whitespace-nowrap">
                            {formatDate(tx.date)}
                          </td>
                          <td className="px-3 py-3">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getApiColor(tx.api)}`}>
                              {getApiLabel(tx.api)}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-sm">
                            <a
                              href={`/cotacao/${tx.quote_id}`}
                              className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                            >
                              #{tx.quote_id}
                            </a>
                          </td>
                          <td className="px-3 py-3 text-sm text-gray-500 dark:text-gray-400 break-words max-w-[112px]">
                            {tx.client_name || '-'}
                          </td>
                          <td className="px-3 py-3 text-sm text-gray-500 dark:text-gray-400 break-words max-w-[112px]">
                            {tx.project_name || '-'}
                          </td>
                          <td className="px-3 py-3 text-sm text-gray-500 dark:text-gray-400 break-words max-w-[96px]">
                            {tx.user_name || '-'}
                          </td>
                          <td className="px-3 py-3 text-sm text-gray-500 dark:text-gray-400 break-words max-w-[192px]">
                            {tx.description}
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                            {formatCurrency(tx.cost_brl)}
                            {tx.cost_usd > 0 && (
                              <span className="block text-xs text-gray-500 dark:text-gray-400">
                                {formatCurrency(tx.cost_usd, 'USD')}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-gray-50 dark:bg-gray-900">
                      <tr>
                        <td colSpan={7} className="px-4 py-4 text-sm font-bold text-gray-900 dark:text-gray-100 text-right">
                          TOTAL:
                        </td>
                        <td className="px-4 py-4 text-sm font-bold text-gray-900 dark:text-gray-100 text-right">
                          {formatCurrency(reportData.total_brl)}
                          {reportData.total_usd > 0 && (
                            <span className="block text-xs text-gray-500 dark:text-gray-400 font-normal">
                              {formatCurrency(reportData.total_usd, 'USD')}
                            </span>
                          )}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {/* Mobile Cards */}
                <div className="md:hidden divide-y divide-gray-200 dark:divide-gray-700">
                  {reportData.transactions.map((tx, idx) => (
                    <a
                      key={`${tx.quote_id}-${tx.api}-${idx}`}
                      href={`/cotacao/${tx.quote_id}`}
                      className="block p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${getApiColor(tx.api)}`}>
                            {getApiLabel(tx.api)}
                          </span>
                          <span className="text-xs text-gray-500 dark:text-gray-400">#{tx.quote_id}</span>
                        </div>
                        <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                          {formatCurrency(tx.cost_brl)}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 truncate">
                        {tx.description}
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500">
                        <span>{formatDate(tx.date)}</span>
                        <span>{tx.client_name || tx.project_name || '-'}</span>
                      </div>
                    </a>
                  ))}
                  {/* Mobile Total */}
                  <div className="p-4 bg-gray-50 dark:bg-gray-900">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-bold text-gray-900 dark:text-gray-100">TOTAL:</span>
                      <span className="text-base font-bold text-gray-900 dark:text-gray-100">
                        {formatCurrency(reportData.total_brl)}
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
      {!hasSearched && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-12 text-center">
          <div className="text-gray-400 dark:text-gray-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
            Selecione os filtros
          </h3>
          <p className="text-gray-500 dark:text-gray-400">
            Escolha um período e/ou integrações e clique em &quot;Exibir&quot; para ver o relatório financeiro.
          </p>
        </div>
      )}
    </div>
    </AdminRoute>
  )
}
