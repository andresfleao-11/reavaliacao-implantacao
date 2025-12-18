'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
import { quotesApi, QuoteDetail, materialsApi, SuggestedMaterial, IntegrationLog, API_URL } from '@/lib/api'
import SearchLogDetail from '@/components/SearchLogDetail'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

export default function QuoteDetailPage() {
  const params = useParams()
  const id = parseInt(params.id as string)
  const [generatingPdf, setGeneratingPdf] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [requoting, setRequoting] = useState(false)
  const [showMaterialModal, setShowMaterialModal] = useState(false)
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [suggestions, setSuggestions] = useState<SuggestedMaterial[]>([])
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [integrationLogs, setIntegrationLogs] = useState<IntegrationLog[]>([])
  const [loadingLogs, setLoadingLogs] = useState(false)
  const [anthropicExpanded, setAnthropicExpanded] = useState(true)
  const [serpApiExpanded, setSerpApiExpanded] = useState(true)
  const [searchLogExpanded, setSearchLogExpanded] = useState(true)
  const [googleShoppingExpanded, setGoogleShoppingExpanded] = useState(false)
  const [fipeExpanded, setFipeExpanded] = useState(true)
  const [fipeApiCallsExpanded, setFipeApiCallsExpanded] = useState(false)
  const [searchStatsExpanded, setSearchStatsExpanded] = useState(false)
  const [expandedFailures, setExpandedFailures] = useState<Set<number>>(new Set())
  const [showPromptModal, setShowPromptModal] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null)
  const [quoteCosts, setQuoteCosts] = useState<{
    anthropic: {
      cost_usd: number;
      cost_brl: number;
      tokens: number;
      calls: number;
    };
    openai: {
      cost_usd: number;
      cost_brl: number;
      tokens: number;
      calls: number;
    };
    serpapi: {
      cost_brl: number;
      cost_per_call: number;
      total_calls: number;
      shopping_calls: number;
      immersive_calls: number;
    };
    total_cost_usd: number;
    total_cost_brl: number;
    usd_to_brl_rate: number;
  } | null>(null)

  const [prevStatus, setPrevStatus] = useState<string | null>(null)

  const { data: quote, error, mutate } = useSWR<QuoteDetail>(
    id ? `/quotes/${id}` : null,
    () => quotesApi.get(id),
    {
      refreshInterval: (data) => {
        return data?.status === 'PROCESSING' ? 3000 : 0
      },
    }
  )

  // Detectar mudança de status de PROCESSING para DONE/ERROR e recarregar dados
  useEffect(() => {
    if (quote?.status && prevStatus === 'PROCESSING' && quote.status !== 'PROCESSING') {
      // Status mudou de PROCESSING para outro - recarregar logs e custos
      setIntegrationLogs([])
      setQuoteCosts(null)
      setLoadingLogs(false)  // Reset loading state para permitir novo carregamento
    }
    if (quote?.status) {
      setPrevStatus(quote.status)
    }
  }, [quote?.status, prevStatus])

  const loadMaterialSuggestions = useCallback(async () => {
    if (!quote?.claude_payload_json?.especificacoes_tecnicas) {
      return
    }

    setLoadingSuggestions(true)
    try {
      const response = await materialsApi.suggestMaterials(
        quote.claude_payload_json.especificacoes_tecnicas,
        quote.claude_payload_json.tipo_produto,
        quote.project_id || undefined
      )
      setSuggestions(response.suggestions)
    } catch (err: any) {
      console.error('Erro ao carregar sugestões:', err)
      alert(err.response?.data?.detail || 'Erro ao buscar materiais sugeridos')
    } finally {
      setLoadingSuggestions(false)
    }
  }, [quote])

  useEffect(() => {
    if (showMaterialModal && suggestions.length === 0 && !loadingSuggestions) {
      loadMaterialSuggestions()
    }
  }, [showMaterialModal, loadMaterialSuggestions, suggestions.length, loadingSuggestions])

  // Load integration logs for any quote (not just DONE)
  useEffect(() => {
    if (quote && integrationLogs.length === 0 && !loadingLogs) {
      setLoadingLogs(true)
      quotesApi.getIntegrationLogs(id)
        .then(setIntegrationLogs)
        .catch(err => console.error('Error loading integration logs:', err))
        .finally(() => setLoadingLogs(false))
    }
  }, [quote, id, integrationLogs.length, loadingLogs])

  // Load quote costs
  useEffect(() => {
    if (quote && !quoteCosts) {
      fetch(`${API_URL}/api/v2/financial/quote/${id}/costs`)
        .then(res => res.json())
        .then(data => setQuoteCosts(data))
        .catch(err => console.error('Error loading quote costs:', err))
    }
  }, [quote, id, quoteCosts])

  const formatCurrency = (value: number | null) => {
    if (value === null) return 'N/A'
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(value)
  }

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })
  }

  const handleCancel = async () => {
    if (!confirm('Tem certeza que deseja cancelar esta cotação?')) {
      return
    }

    setCancelling(true)
    try {
      await quotesApi.cancel(id)
      mutate()
    } catch (err: any) {
      console.error('Erro ao cancelar cotação:', err)
      alert(err.response?.data?.detail || 'Erro ao cancelar cotação')
    } finally {
      setCancelling(false)
    }
  }

  const handleRequote = async () => {
    setRequoting(true)
    try {
      const result = await quotesApi.requote(id)
      window.location.href = `/cotacao/${result.quoteRequestId}`
    } catch (err: any) {
      console.error('Erro ao recotar:', err)
      alert(err.response?.data?.detail || 'Erro ao criar nova cotação')
      setRequoting(false)
    }
  }

  const handleGeneratePdf = async () => {
    setGeneratingPdf(true)
    try {
      await quotesApi.generatePdf(id)
      mutate()
    } catch (err: any) {
      console.error('Erro ao gerar PDF:', err)
      alert('Erro ao gerar PDF')
    } finally {
      setGeneratingPdf(false)
    }
  }

  const handleOpenMaterialModal = () => {
    setShowMaterialModal(true)
  }

  const handleCloseMaterialModal = () => {
    setShowMaterialModal(false)
    setSelectedMaterialId(null)
    setSuggestions([])
  }

  const handleSelectMaterial = (materialId: number) => {
    setSelectedMaterialId(materialId)
  }

  const handleConfirmLinkMaterial = () => {
    if (selectedMaterialId) {
      alert(`Funcionalidade de vinculação será implementada.\nMaterial ID: ${selectedMaterialId}`)
      setShowMaterialModal(false)
      setSelectedMaterialId(null)
    }
  }

  if (error) {
    return (
      <div className="max-w-6xl">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg">
          Erro ao carregar cotação
        </div>
      </div>
    )
  }

  if (!quote) {
    return (
      <div className="max-w-6xl">
        <div className="card">
          <p className="text-gray-600 dark:text-gray-400">Carregando...</p>
        </div>
      </div>
    )
  }

  // Helper para exibir tipo de entrada
  const getInputTypeInfo = (inputType: string | null) => {
    switch (inputType) {
      case 'TEXT':
        return { label: 'Texto', icon: '📝', color: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200' }
      case 'IMAGE':
        return { label: 'Imagem', icon: '📷', color: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' }
      case 'GOOGLE_LENS':
        return { label: 'Google Lens', icon: '🔍', color: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200' }
      default:
        return { label: 'Texto', icon: '📝', color: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200' }
    }
  }

  const inputTypeInfo = getInputTypeInfo(quote.input_type)

  return (
    <div className="max-w-6xl">
      {/* Header responsivo: título em uma linha, tags abaixo */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-gray-900 dark:text-gray-100">
          Cotação #{quote.id}
          {quote.attempt_number > 1 && (
            <span className="ml-2 text-xs sm:text-sm font-normal text-gray-500 dark:text-gray-400">
              (Tentativa {quote.attempt_number})
            </span>
          )}
        </h1>

        {/* Tags e botões em linha separada */}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          {/* Tag de Lote */}
          {quote.batch_job_id && (
            <Link
              href={`/cotacao/lote/${quote.batch_job_id}`}
              className="px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-medium bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-200 hover:bg-cyan-200 dark:hover:bg-cyan-900/50 transition-colors"
              title="Ver lote completo"
            >
              📦 Lote #{quote.batch_job_id}
            </Link>
          )}

          {/* Tipo de Entrada */}
          <span
            className={`px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-medium ${inputTypeInfo.color}`}
            title={`Tipo de entrada: ${inputTypeInfo.label}`}
          >
            {inputTypeInfo.icon} {inputTypeInfo.label}
          </span>

          {/* Status */}
          <span
            className={`px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-medium ${
              quote.status === 'DONE'
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                : quote.status === 'PROCESSING'
                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                : quote.status === 'CANCELLED'
                ? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
            }`}
          >
            {quote.status === 'DONE'
              ? 'Concluída'
              : quote.status === 'PROCESSING'
              ? 'Processando'
              : quote.status === 'CANCELLED'
              ? 'Cancelada'
              : 'Erro'}
          </span>

          {/* Botão de cancelar para cotações em andamento */}
          {quote.status === 'PROCESSING' && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {cancelling ? 'Cancelando...' : 'Cancelar'}
            </button>
          )}

          {/* Botão de recotar para cotações canceladas, com erro ou aguardando revisão - somente se não foi recotado */}
          {(quote.status === 'CANCELLED' || quote.status === 'ERROR' || quote.status === 'AWAITING_REVIEW') && !quote.child_quote_id && (
            <button
              onClick={handleRequote}
              disabled={requoting}
              className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {requoting ? 'Iniciando...' : 'Recotar'}
            </button>
          )}

          {/* Link para nova cotação quando já foi recotado */}
          {(quote.status === 'CANCELLED' || quote.status === 'ERROR' || quote.status === 'AWAITING_REVIEW') && quote.child_quote_id && (
            <Link
              href={`/cotacao/${quote.child_quote_id}`}
              className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex items-center"
            >
              <svg className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              #{quote.child_quote_id}
            </Link>
          )}
        </div>
      </div>

      {quote.status === 'PROCESSING' && (
        <div className="mb-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-5">
          <div className="space-y-3">
            {/* Texto descritivo */}
            <div className="flex items-center justify-between">
              <div className="flex items-center flex-1">
                <svg className="animate-spin h-5 w-5 mr-3 text-blue-600 dark:text-blue-400 flex-shrink-0" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {quote.step_details || 'Processando cotação...'}
                </span>
              </div>
              <span className="text-sm font-semibold text-blue-600 dark:text-blue-400 ml-4">
                {quote.progress_percentage || 0}%
              </span>
            </div>

            {/* Barra de progresso */}
            <div className="relative">
              <div className="overflow-hidden h-2.5 text-xs flex rounded-full bg-blue-100 dark:bg-blue-900/40">
                <div
                  style={{ width: `${quote.progress_percentage || 0}%` }}
                  className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300 ease-out"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {quote.status === 'CANCELLED' && (
        <div className="mb-6 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 px-4 py-3 rounded-lg">
          <div className="flex items-center">
            <svg className="h-5 w-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            {quote.error_message || 'Cotação cancelada'}
          </div>
        </div>
      )}

      {quote.status === 'ERROR' && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg">
          <div className="flex items-center">
            <svg className="h-5 w-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Erro: {quote.error_message || 'Erro desconhecido'}
          </div>
        </div>
      )}

      {/* Detectar se é cotação FIPE (veículo) */}
      {(() => {
        const isFipeQuote = quote.sources?.some(s => s.domain === 'fipe.org.br') ||
                           quote.claude_payload_json?.fipe_result?.success ||
                           quote.claude_payload_json?.natureza?.includes('veiculo');
        const fipeRefMonth = quote.claude_payload_json?.fipe_result?.price?.referenceMonth;

        if (isFipeQuote) {
          return (
            <div className="mb-6">
              <div className="card bg-gradient-to-r from-blue-50 to-green-50 dark:from-blue-900/20 dark:to-green-900/20 border border-blue-200 dark:border-blue-800">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Valor Tabela FIPE {fipeRefMonth && <span className="text-sm font-normal text-gray-500 dark:text-gray-400">({fipeRefMonth})</span>}
                </h3>
                <p className="text-3xl font-bold text-green-600 dark:text-green-400">{formatCurrency(quote.valor_medio)}</p>
              </div>
            </div>
          );
        }

        return (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-6 mb-6">
            <div className="card p-3 sm:p-4">
              <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1 sm:mb-2">Valor Médio</h3>
              <p className="text-xl sm:text-3xl font-bold text-primary-600 dark:text-primary-400">{formatCurrency(quote.valor_medio)}</p>
            </div>
            <div className="card p-3 sm:p-4">
              <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1 sm:mb-2">Valor Mínimo</h3>
              <p className="text-lg sm:text-2xl font-semibold text-gray-700 dark:text-gray-300">{formatCurrency(quote.valor_minimo)}</p>
            </div>
            <div className="card p-3 sm:p-4">
              <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1 sm:mb-2">Valor Máximo</h3>
              <p className="text-lg sm:text-2xl font-semibold text-gray-700 dark:text-gray-300">{formatCurrency(quote.valor_maximo)}</p>
            </div>
          </div>
        );
      })()}

      {/* Informações do Projeto */}
      {quote.project && (
        <div className="card mb-4 sm:mb-6 p-3 sm:p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <h2 className="text-base sm:text-xl font-bold text-gray-900 dark:text-gray-100 mb-2 sm:mb-4">Projeto Vinculado</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
            <div>
              <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Projeto</p>
              <Link
                href={`/cadastros/projetos/${quote.project.id}`}
                className="text-sm sm:text-base text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 font-medium"
              >
                {quote.project.nome}
              </Link>
            </div>
            {quote.project.cliente_nome && (
              <div>
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Cliente</p>
                <p className="text-sm sm:text-base text-gray-900 dark:text-gray-100">{quote.project.cliente_nome}</p>
              </div>
            )}
            {quote.project.config_versao && (
              <div>
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Versão Config</p>
                <p className="text-sm sm:text-base text-gray-900 dark:text-gray-100">v{quote.project.config_versao}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {quote.claude_payload_json && (
        <div className="card mb-4 sm:mb-6 p-3 sm:p-4">
          <h2 className="text-base sm:text-xl font-bold text-gray-900 dark:text-gray-100 mb-2 sm:mb-4">Análise do Item</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4 mb-2 sm:mb-4">
            <div>
              <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Nome</p>
              <p className="text-sm sm:text-base text-gray-900 dark:text-gray-100">{quote.claude_payload_json.nome_canonico || 'N/A'}</p>
            </div>
            {quote.claude_payload_json.marca && (
              <div>
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Marca</p>
                <p className="text-sm sm:text-base text-gray-900 dark:text-gray-100">{quote.claude_payload_json.marca}</p>
              </div>
            )}
            {quote.claude_payload_json.modelo && (
              <div>
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Modelo</p>
                <p className="text-sm sm:text-base text-gray-900 dark:text-gray-100">{quote.claude_payload_json.modelo}</p>
              </div>
            )}
            {quote.codigo_item && (
              <div>
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400">Código</p>
                <p className="text-sm sm:text-base text-gray-900 dark:text-gray-100">{quote.codigo_item}</p>
              </div>
            )}
          </div>

          {/* Especificações Técnicas */}
          {quote.claude_payload_json.especificacoes_tecnicas &&
           Object.keys(quote.claude_payload_json.especificacoes_tecnicas).length > 0 && (
            <div className="border-t border-gray-200 dark:border-gray-700 pt-3 sm:pt-4 mt-3 sm:mt-4">
              <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3">Especificações Técnicas</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
                {Object.entries(quote.claude_payload_json.especificacoes_tecnicas).map(([key, value]) => (
                  <div key={key} className="bg-gray-50 dark:bg-gray-700 p-2 sm:p-3 rounded-lg">
                    <p className="text-[10px] sm:text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {key.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs sm:text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {String(value)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Material e Características */}
      {quote.status === 'DONE' && quote.claude_payload_json && (
        <div className="card mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Material e Características</h2>
            <button
              className="btn-primary flex items-center"
              onClick={handleOpenMaterialModal}
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              Vincular com Tabela de Materiais
            </button>
          </div>

          <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Nenhum material vinculado. Clique em "Vincular com Tabela de Materiais" para associar este item a um material cadastrado ou criar um novo.
            </p>
          </div>
        </div>
      )}

      {quote.search_query_final && (
        <div className="card mb-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Query de Busca</h2>
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
            <code className="text-sm text-gray-800 dark:text-gray-200">{quote.search_query_final}</code>
          </div>
        </div>
      )}

      {/* Botão de PDF - sempre visível quando DONE */}
      {quote.status === 'DONE' ? (
        <div className="card mb-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Relatório PDF</h2>
            {quote.pdf_url ? (
              <a
                href={quotesApi.downloadPdf(quote.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
              >
                Baixar PDF
              </a>
            ) : (
              <button
                onClick={handleGeneratePdf}
                disabled={generatingPdf}
                className="btn-primary disabled:opacity-50"
              >
                {generatingPdf ? 'Gerando...' : 'Gerar PDF'}
              </button>
            )}
          </div>
        </div>
      ) : null}

      {quote.sources && quote.sources.length > 0 && (
        <div className="card mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Cotações Encontradas</h2>
          </div>

          {(() => {
            const isFipeQuote = quote.sources?.some(s => s.domain === 'fipe.org.br') ||
                               quote.claude_payload_json?.fipe_result?.success ||
                               quote.claude_payload_json?.natureza?.includes('veiculo');
            return (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-900">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        {isFipeQuote ? 'Fonte' : 'Loja'}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Preço</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Data</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {quote.sources.map((source) => (
                      <tr key={source.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                          {source.domain === 'fipe.org.br' ? 'Tabela FIPE' : (source.domain || 'N/A')}
                        </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {formatCurrency(source.price_value)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(source.captured_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {source.is_outlier ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
                          Outlier
                        </span>
                      ) : source.is_accepted ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                          Aceita
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs rounded-full bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
                          Rejeitada
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300"
                      >
                        Ver
                      </a>
                    </td>
                  </tr>
                ))}
                    </tbody>
                  </table>
                </div>
              );
            })()}

          {quote.sources.some((s) => s.screenshot_url) && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Evidências (Screenshots)</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {quote.sources
                  .filter((s) => s.screenshot_url)
                  .map((source) => (
                    <div key={source.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        {source.domain === 'fipe.org.br' ? 'Tabela FIPE' : source.domain}
                      </p>
                      <img
                        src={`${API_URL}${source.screenshot_url}`}
                        alt={`Screenshot ${source.domain}`}
                        className="w-full rounded-lg max-h-[40vh] object-contain"
                      />
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Informações Adicionais</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Local</p>
            <p className="text-gray-900 dark:text-gray-100">{quote.local || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Pesquisador</p>
            <p className="text-gray-900 dark:text-gray-100">{quote.pesquisador || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Data de Criação</p>
            <p className="text-gray-900 dark:text-gray-100">{formatDate(quote.created_at)}</p>
          </div>
        </div>
      </div>

      {/* Variação da Cotação */}
      {(quote.status === 'DONE' || quote.status === 'AWAITING_REVIEW') && (
        <div className="card mt-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Variação da Cotação</h2>
          {(() => {
            const isFipeQuote = quote.sources?.some(s => s.domain === 'fipe.org.br') ||
                               quote.claude_payload_json?.fipe_result?.success ||
                               quote.claude_payload_json?.natureza?.includes('veiculo');

            if (isFipeQuote) {
              return (
                <div className="border rounded-lg p-4 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
                  <div className="flex items-center gap-3">
                    <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-blue-700 dark:text-blue-300 font-medium">
                      Não se aplica para veículos
                    </p>
                  </div>
                  <p className="text-sm text-blue-600 dark:text-blue-400 mt-2">
                    Cotações de veículos utilizam a Tabela FIPE como referência única de preço.
                  </p>
                </div>
              );
            }

            if (quote.variacao_percentual === null) return null;

            return (
              <div className={`border rounded-lg p-4 ${
                quote.variacao_percentual <= (quote.variacao_maxima_percent || 25)
                  ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                  : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
              }`}>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className={`text-sm font-medium ${
                      quote.variacao_percentual <= (quote.variacao_maxima_percent || 25)
                        ? 'text-green-700 dark:text-green-300'
                        : 'text-red-700 dark:text-red-300'
                    }`}>Variação Calculada</p>
                    <p className={`text-2xl font-bold ${
                      quote.variacao_percentual <= (quote.variacao_maxima_percent || 25)
                        ? 'text-green-900 dark:text-green-100'
                        : 'text-red-900 dark:text-red-100'
                    }`}>{quote.variacao_percentual.toFixed(2)}%</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Variação Máxima Configurada</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{quote.variacao_maxima_percent || 25}%</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Cotações Configuradas</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{quote.numero_cotacoes_configurado || 3}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Fórmula</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">(MAX / MIN - 1) × 100</p>
                  </div>
                </div>
                <p className={`text-xs mt-3 ${
                  quote.variacao_percentual <= (quote.variacao_maxima_percent || 25)
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-red-600 dark:text-red-400'
                }`}>
                  {quote.variacao_percentual <= (quote.variacao_maxima_percent || 25)
                    ? '✓ Variação dentro do limite aceitável'
                    : '⚠ Variação acima do limite configurado'}
                </p>
              </div>
            );
          })()}
        </div>
      )}

      {/* Histórico de Tentativas - Mostrar se houver mais de uma tentativa */}
      {quote.attempt_history && quote.attempt_history.length > 1 && (
        <div className="card mt-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">
            Histórico de Tentativas
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Tentativa
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Cotação
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Data
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Observação
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {quote.attempt_history.map((attempt) => (
                  <tr
                    key={attempt.id}
                    className={attempt.id === quote.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}
                  >
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 font-medium">
                      #{attempt.attempt_number}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {attempt.id === quote.id ? (
                        <span className="text-gray-900 dark:text-gray-100 font-medium">
                          #{attempt.id} (atual)
                        </span>
                      ) : (
                        <a
                          href={`/cotacao/${attempt.id}`}
                          className="text-primary-600 hover:text-primary-800"
                        >
                          #{attempt.id}
                        </a>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      {formatDate(attempt.created_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center">
                      {attempt.status === 'DONE' ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                          Concluída
                        </span>
                      ) : attempt.status === 'PROCESSING' ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                          Processando
                        </span>
                      ) : attempt.status === 'CANCELLED' ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                          Cancelada
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                          Erro
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate" title={attempt.error_message || ''}>
                      {attempt.error_message || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Integration Logs Section - Show for all statuses */}
      {integrationLogs.length > 0 && (
        <div className="card mt-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Integrações</h2>

          {/* Cost Summary */}
          {quoteCosts && (quoteCosts.total_cost_usd > 0 || quoteCosts.total_cost_brl > 0) && (
            <div className="mb-4 sm:mb-6 p-3 sm:p-4 bg-gradient-to-r from-blue-50 to-green-50 dark:from-blue-900/20 dark:to-green-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1 sm:gap-0 mb-3">
                <h3 className="text-xs sm:text-sm font-semibold text-gray-700 dark:text-gray-300">Custos desta Cotação</h3>
                <span className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">
                  Taxa: 1 USD = R$ {quoteCosts.usd_to_brl_rate.toFixed(2)}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                {/* Anthropic */}
                {quoteCosts.anthropic.calls > 0 && (
                  <div className="text-center p-2 sm:p-0 bg-white/50 dark:bg-gray-800/50 rounded-lg sm:bg-transparent sm:rounded-none">
                    <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Anthropic</p>
                    <p className="text-[10px] sm:text-xs text-gray-400 dark:text-gray-500">({quoteCosts.anthropic.tokens.toLocaleString()} tokens)</p>
                    <p className="text-sm sm:text-lg font-bold text-orange-600 dark:text-orange-400">
                      R$ {quoteCosts.anthropic.cost_brl.toFixed(2)}
                    </p>
                  </div>
                )}
                {/* OpenAI */}
                {quoteCosts.openai.calls > 0 && (
                  <div className="text-center p-2 sm:p-0 bg-white/50 dark:bg-gray-800/50 rounded-lg sm:bg-transparent sm:rounded-none">
                    <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">OpenAI</p>
                    <p className="text-[10px] sm:text-xs text-gray-400 dark:text-gray-500">({quoteCosts.openai.tokens.toLocaleString()} tokens)</p>
                    <p className="text-sm sm:text-lg font-bold text-blue-600 dark:text-blue-400">
                      R$ {quoteCosts.openai.cost_brl.toFixed(2)}
                    </p>
                  </div>
                )}
                {/* SerpAPI */}
                {quoteCosts.serpapi.total_calls > 0 && (
                  <div className="text-center p-2 sm:p-0 bg-white/50 dark:bg-gray-800/50 rounded-lg sm:bg-transparent sm:rounded-none">
                    <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">SerpAPI</p>
                    <p className="text-[10px] sm:text-xs text-gray-400 dark:text-gray-500">
                      ({quoteCosts.serpapi.shopping_calls}+{quoteCosts.serpapi.immersive_calls})
                    </p>
                    <p className="text-sm sm:text-lg font-bold text-green-600 dark:text-green-400">
                      R$ {quoteCosts.serpapi.cost_brl.toFixed(2)}
                    </p>
                  </div>
                )}
                {/* Total */}
                <div className="text-center p-2 sm:p-0 sm:border-l sm:border-gray-300 sm:dark:border-gray-600 sm:pl-4 bg-primary-50 dark:bg-primary-900/30 rounded-lg sm:bg-transparent sm:rounded-none col-span-2 sm:col-span-1">
                  <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Total</p>
                  <p className="text-[10px] sm:text-xs text-gray-400 dark:text-gray-500">
                    $ {quoteCosts.total_cost_usd.toFixed(4)} USD
                  </p>
                  <p className="text-base sm:text-lg font-bold text-gray-900 dark:text-gray-100">
                    R$ {quoteCosts.total_cost_brl.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Search Log Summary */}
          {integrationLogs.some(log => log.integration_type === 'search_log') && (
            <div className="mb-4 sm:mb-6">
              <button
                onClick={() => setSearchLogExpanded(!searchLogExpanded)}
                className="w-full flex items-center justify-between text-sm sm:text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2 sm:mb-3 hover:text-primary-600 transition-colors"
              >
                <span>📊 Log de Busca</span>
                <svg
                  className={`w-4 h-4 sm:w-5 sm:h-5 transform transition-transform ${searchLogExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {searchLogExpanded && integrationLogs
                .filter(log => log.integration_type === 'search_log')
                .map(log => {
                  const summary = log.response_summary || {}
                  return (
                    <div key={log.id} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 sm:p-4">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 mb-3 sm:mb-4">
                        <div className="text-center p-2 bg-white dark:bg-gray-700 rounded-lg">
                          <p className="text-[10px] sm:text-xs font-medium text-gray-500 dark:text-gray-400">Produtos</p>
                          <p className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">{summary.total_raw_products || 0}</p>
                        </div>
                        <div className="text-center p-2 bg-white dark:bg-gray-700 rounded-lg">
                          <p className="text-[10px] sm:text-xs font-medium text-gray-500 dark:text-gray-400">Após Filtro</p>
                          <p className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">{summary.after_source_filter || 0}</p>
                        </div>
                        <div className="text-center p-2 bg-white dark:bg-gray-700 rounded-lg">
                          <p className="text-[10px] sm:text-xs font-medium text-gray-500 dark:text-gray-400">Blocos</p>
                          <p className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">{summary.valid_blocks || 0}</p>
                        </div>
                        <div className="text-center p-2 bg-green-50 dark:bg-green-900/30 rounded-lg">
                          <p className="text-[10px] sm:text-xs font-medium text-gray-500 dark:text-gray-400">Obtidos</p>
                          <p className="text-base sm:text-lg font-semibold text-green-600 dark:text-green-400">{summary.results_obtained || 0}</p>
                        </div>
                      </div>
                      {summary.block_details && summary.block_details.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Detalhes dos Blocos Tentados:</p>
                          <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead className="bg-gray-100 dark:bg-gray-700">
                                <tr>
                                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Bloco</th>
                                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Produtos</th>
                                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Faixa de Preço</th>
                                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Cotações</th>
                                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                                </tr>
                              </thead>
                              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                {summary.block_details.map((block: any, idx: number) => (
                                  <tr key={idx}>
                                    <td className="px-3 py-2 text-sm text-gray-900 dark:text-gray-100">#{block.index}</td>
                                    <td className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">{block.size}</td>
                                    <td className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">
                                      R$ {block.min_price?.toFixed(2)} - R$ {block.max_price?.toFixed(2)}
                                    </td>
                                    <td className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">
                                      {block.results_obtained}/{summary.limit || 3}
                                    </td>
                                    <td className="px-3 py-2 text-sm">
                                      {block.result === 'success' ? (
                                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                          ✓ Sucesso
                                        </span>
                                      ) : (
                                        <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                                          ✗ Falhou
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          )}

          {/* AI Provider (Anthropic/OpenAI) Logs */}
          {integrationLogs.some(log => log.integration_type === 'anthropic' || log.integration_type === 'openai') && (
            <div className="mb-6">
              <button
                onClick={() => setAnthropicExpanded(!anthropicExpanded)}
                className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
              >
                <span>
                  {integrationLogs.some(log => log.integration_type === 'openai')
                    ? '🤖 OpenAI (GPT)'
                    : '🤖 Anthropic (Claude)'}
                </span>
                <svg
                  className={`w-5 h-5 transform transition-transform ${anthropicExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {anthropicExpanded && (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Chamada API</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Atividade</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Modelo</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Tokens</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Custo (USD)</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Prompt</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {integrationLogs
                        .filter(log => log.integration_type === 'anthropic' || log.integration_type === 'openai')
                        .map((log, idx) => (
                          <tr key={log.id}>
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">#{idx + 1}</td>
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">{log.activity}</td>
                            <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{log.model_used}</td>
                            <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">
                              {log.total_tokens?.toLocaleString()}
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">
                              ${log.estimated_cost_usd?.toFixed(6)}
                            </td>
                            <td className="px-4 py-3 text-sm text-center">
                              <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                ✓ OK
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-center">
                              {log.request_data?.prompt ? (
                                <button
                                  onClick={() => {
                                    setSelectedPrompt(log.request_data?.prompt || null)
                                    setShowPromptModal(true)
                                  }}
                                  className="text-primary-600 hover:text-primary-800 dark:text-primary-400 dark:hover:text-primary-300 underline"
                                >
                                  ver
                                </button>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      <tr className="bg-gray-50 dark:bg-gray-700 font-semibold">
                        <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100" colSpan={3}>Total</td>
                        <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">
                          {integrationLogs
                            .filter(log => log.integration_type === 'anthropic' || log.integration_type === 'openai')
                            .reduce((sum, log) => sum + (log.total_tokens || 0), 0)
                            .toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-gray-900 dark:text-gray-100">
                          ${integrationLogs
                            .filter(log => log.integration_type === 'anthropic' || log.integration_type === 'openai')
                            .reduce((sum, log) => sum + (log.estimated_cost_usd || 0), 0)
                            .toFixed(6)}
                        </td>
                        <td colSpan={2}></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* SerpAPI Logs */}
          {integrationLogs.some(log => log.integration_type === 'serpapi') && (
            <div>
              <button
                onClick={() => setSerpApiExpanded(!serpApiExpanded)}
                className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
              >
                <span>🔍 SerpAPI ({integrationLogs.filter(log => log.integration_type === 'serpapi').length} chamadas)</span>
                <svg
                  className={`w-5 h-5 transform transition-transform ${serpApiExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {serpApiExpanded && (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Chamada API</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Atividade</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">API</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Link API</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Link Produto</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {integrationLogs
                        .filter(log => log.integration_type === 'serpapi')
                        .map((log, idx) => (
                          <tr key={log.id}>
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">#{idx + 1}</td>
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 max-w-xs truncate" title={log.activity || ''}>
                              {log.activity}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{log.api_used}</td>
                            <td className="px-4 py-3 text-sm text-center">
                              <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                ✓ OK
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {log.search_url && (
                                <a
                                  href={log.search_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary-600 hover:text-primary-800"
                                >
                                  Ver
                                </a>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {log.product_link && (
                                <a
                                  href={log.product_link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary-600 hover:text-primary-800"
                                >
                                  Produto
                                </a>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Banco de Preço de Veículos (from cache) */}
          {integrationLogs.some(log => log.integration_type === 'vehicle_price_bank') && (
            <div className="mb-6">
              <button
                onClick={() => setFipeExpanded(!fipeExpanded)}
                className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
              >
                <span>🏦 Banco de Preço de Veículos</span>
                <svg
                  className={`w-5 h-5 transform transition-transform ${fipeExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {fipeExpanded && integrationLogs
                .filter(log => log.integration_type === 'vehicle_price_bank')
                .map(log => {
                  const bankData = log.response_summary || {}
                  return (
                    <div key={log.id} className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 space-y-4 border border-blue-200 dark:border-blue-800">
                      {/* Status e Resumo */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="px-3 py-1 text-sm rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                            💾 Cache Vigente
                          </span>
                          <span className="text-sm text-gray-600 dark:text-gray-400">
                            0 chamadas à API (dados do cache)
                          </span>
                        </div>
                        {bankData.price && (
                          <div className="text-right">
                            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                              {bankData.price.price}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              Ref: {bankData.price.referenceMonth}
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Informações do Cache */}
                      {bankData.cached_at && (
                        <div className="p-2 bg-blue-100 dark:bg-blue-800/30 rounded text-sm text-blue-700 dark:text-blue-300">
                          📅 Cotação em cache desde: {new Date(bankData.cached_at).toLocaleString('pt-BR')}
                        </div>
                      )}

                      {/* Dados do Veículo */}
                      {bankData.price && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-3 bg-white dark:bg-gray-700 rounded-lg">
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Código FIPE</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {bankData.codigo_fipe || bankData.price.codeFipe}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Marca</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {bankData.brand_name || bankData.price.brand}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Modelo</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {bankData.model_name || bankData.price.model}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Ano/Combustível</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {bankData.year_model || bankData.price.modelYear} - {bankData.fuel_type || bankData.price.fuel}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Screenshot do cache */}
                      {bankData.screenshot_path && (
                        <div className="p-2 bg-green-50 dark:bg-green-900/20 rounded text-sm text-green-700 dark:text-green-300">
                          📸 Screenshot disponível no cache
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          )}

          {/* FIPE API Logs (for vehicles - when called API directly) */}
          {integrationLogs.some(log => log.integration_type === 'fipe') && (
            <div className="mb-6">
              <button
                onClick={() => setFipeExpanded(!fipeExpanded)}
                className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
              >
                <span>🚗 API FIPE (Tabela FIPE)</span>
                <svg
                  className={`w-5 h-5 transform transition-transform ${fipeExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {fipeExpanded && integrationLogs
                .filter(log => log.integration_type === 'fipe')
                .map(log => {
                  const fipeData = log.response_summary || {}
                  return (
                    <div key={log.id} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-4">
                      {/* Status e Resumo */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {fipeData.success ? (
                            <span className="px-3 py-1 text-sm rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                              ✓ Sucesso
                            </span>
                          ) : (
                            <span className="px-3 py-1 text-sm rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                              ✗ Falhou
                            </span>
                          )}
                          <span className="text-sm text-gray-600 dark:text-gray-400">
                            {fipeData.api_calls || 0} chamadas à API
                          </span>
                        </div>
                        {fipeData.price && (
                          <div className="text-right">
                            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                              {fipeData.price.price}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              Ref: {fipeData.price.referenceMonth}
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Dados do Veículo Encontrado */}
                      {fipeData.price && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-3 bg-white dark:bg-gray-700 rounded-lg">
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Código FIPE</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {fipeData.price.codeFipe}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Marca</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {fipeData.price.brand}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Modelo</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {fipeData.price.model}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Ano/Combustível</p>
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {fipeData.price.modelYear} - {fipeData.price.fuel} ({fipeData.price.fuelAcronym})
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Caminho da Busca - Retratil */}
                      {fipeData.search_path && fipeData.search_path.length > 0 && (
                        <div>
                          <button
                            onClick={() => setFipeApiCallsExpanded(!fipeApiCallsExpanded)}
                            className="w-full flex items-center justify-between text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
                          >
                            <span>Chamadas à API ({fipeData.search_path.length})</span>
                            <svg
                              className={`w-4 h-4 transform transition-transform ${fipeApiCallsExpanded ? 'rotate-180' : ''}`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                          {fipeApiCallsExpanded && (
                            <div className="bg-gray-100 dark:bg-gray-900 rounded-lg p-3 max-h-48 overflow-y-auto">
                              <ol className="list-decimal list-inside space-y-1">
                                {fipeData.search_path.map((call: string, idx: number) => (
                                  <li key={idx} className="text-xs font-mono text-gray-600 dark:text-gray-400">
                                    {call}
                                  </li>
                                ))}
                              </ol>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Dados de busca */}
                      {(fipeData.brand_name || fipeData.model_name) && (
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          {fipeData.brand_name && (
                            <div>
                              <p className="text-xs text-gray-500 dark:text-gray-400">Marca Encontrada</p>
                              <p className="font-medium text-gray-900 dark:text-gray-100">{fipeData.brand_name}</p>
                              {fipeData.brand_id && (
                                <p className="text-xs text-gray-400">ID: {fipeData.brand_id}</p>
                              )}
                            </div>
                          )}
                          {fipeData.model_name && (
                            <div>
                              <p className="text-xs text-gray-500 dark:text-gray-400">Modelo Encontrado</p>
                              <p className="font-medium text-gray-900 dark:text-gray-100">{fipeData.model_name}</p>
                              {fipeData.model_id && (
                                <p className="text-xs text-gray-400">ID: {fipeData.model_id}</p>
                              )}
                            </div>
                          )}
                          {fipeData.year_id && (
                            <div>
                              <p className="text-xs text-gray-500 dark:text-gray-400">Ano Selecionado</p>
                              <p className="font-medium text-gray-900 dark:text-gray-100">{fipeData.year_id}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Erro se houver */}
                      {fipeData.error_message && (
                        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                          <p className="text-sm text-red-700 dark:text-red-300">
                            <strong>Erro:</strong> {fipeData.error_message}
                          </p>
                        </div>
                      )}

                      {/* Botão para download do JSON completo */}
                      <div className="flex justify-end">
                        <button
                          onClick={() => {
                            const dataStr = JSON.stringify(fipeData, null, 2)
                            const blob = new Blob([dataStr], { type: 'application/json' })
                            const url = URL.createObjectURL(blob)
                            const a = document.createElement('a')
                            a.href = url
                            a.download = `cotacao_${quote.id}_fipe.json`
                            document.body.appendChild(a)
                            a.click()
                            document.body.removeChild(a)
                            URL.revokeObjectURL(url)
                          }}
                          className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
                        >
                          Download JSON FIPE
                        </button>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}

          {/* Google Shopping JSON Response */}
          {quote.google_shopping_response_json && (
            <div className="mb-6">
              <button
                onClick={() => setGoogleShoppingExpanded(!googleShoppingExpanded)}
                className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
              >
                <span>🛒 JSON Google Shopping</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      const dataStr = JSON.stringify(quote.google_shopping_response_json, null, 2)
                      const blob = new Blob([dataStr], { type: 'application/json' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `cotacao_${quote.id}_google_shopping.json`
                      document.body.appendChild(a)
                      a.click()
                      document.body.removeChild(a)
                      URL.revokeObjectURL(url)
                    }}
                    className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
                  >
                    Download JSON
                  </button>
                  <svg
                    className={`w-5 h-5 transform transition-transform ${googleShoppingExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>
              {googleShoppingExpanded && (
                <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 overflow-auto max-h-96">
                  <pre className="text-xs text-gray-700 dark:text-gray-300 font-mono whitespace-pre-wrap">
                    {JSON.stringify(quote.google_shopping_response_json, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Log de Busca Detalhado - Seção separada no final da página */}
      {quote?.google_shopping_response_json?.search_stats && (
        <div className="card mt-6">
          <button
            onClick={() => setSearchStatsExpanded(!searchStatsExpanded)}
            className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
          >
            <span>📊 Log de Busca Detalhado</span>
            <svg
              className={`w-5 h-5 transform transition-transform ${searchStatsExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {searchStatsExpanded && (
            <SearchLogDetail
              searchStats={quote.google_shopping_response_json.search_stats}
              shoppingLog={quote.google_shopping_response_json.shopping_log || {}}
            />
          )}
        </div>
      )}

      {/* LEGACY: Log de Busca Detalhado Antigo (mantido para referência, removido do render) */}
      {false && quote?.google_shopping_response_json?.search_stats && (() => {
            const searchStats = quote.google_shopping_response_json.search_stats
            const shoppingLog = quote.google_shopping_response_json.shopping_log || {}
            return (
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                {/* Statistics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div className="bg-white dark:bg-gray-700 rounded-lg p-3 text-center">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Produtos Retornados</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{shoppingLog.total_raw_products || 0}</p>
                  </div>
                  <div className="bg-white dark:bg-gray-700 rounded-lg p-3 text-center">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Após Filtro Fontes</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{shoppingLog.after_source_filter || 0}</p>
                  </div>
                  <div className="bg-white dark:bg-gray-700 rounded-lg p-3 text-center">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Produtos Testados</p>
                    <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{searchStats.products_tested || 0}</p>
                  </div>
                  <div className="bg-white dark:bg-gray-700 rounded-lg p-3 text-center">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Blocos Calculados</p>
                    <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{searchStats.blocks_recalculated || 0}</p>
                  </div>
                </div>

                {/* Summary Stats */}
                <div className="flex flex-wrap gap-4 mb-4 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-green-500"></span>
                    <span className="text-gray-600 dark:text-gray-400">Sucesso: {searchStats.final_valid_sources || 0}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-500"></span>
                    <span className="text-gray-600 dark:text-gray-400">Falhas: {searchStats.final_failed_products || 0}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                    <span className="text-gray-600 dark:text-gray-400">Immersive API: {searchStats.immersive_api_calls || 0} chamadas</span>
                  </div>
                </div>

                {/* Price Mismatch Validation Status */}
                {searchStats.enable_price_mismatch !== undefined && (
                  <div className={`mb-4 p-3 rounded-lg border ${searchStats.enable_price_mismatch
                    ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                    : 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'}`}>
                    <div className="flex items-center gap-2">
                      <span className={`text-lg ${searchStats.enable_price_mismatch ? 'text-green-600' : 'text-yellow-600'}`}>
                        {searchStats.enable_price_mismatch ? '✓' : '⚠'}
                      </span>
                      <div>
                        <p className={`font-medium ${searchStats.enable_price_mismatch
                          ? 'text-green-800 dark:text-green-200'
                          : 'text-yellow-800 dark:text-yellow-200'}`}>
                          Validação de Preço: {searchStats.enable_price_mismatch ? 'HABILITADA' : 'DESABILITADA'}
                        </p>
                        <p className={`text-sm ${searchStats.enable_price_mismatch
                          ? 'text-green-700 dark:text-green-300'
                          : 'text-yellow-700 dark:text-yellow-300'}`}>
                          {searchStats.price_mismatch_note || (searchStats.enable_price_mismatch
                            ? 'Produtos com diferença > 5% entre preço Google e Site são rejeitados'
                            : 'Usando preço do Google Shopping (consistente com seleção de bloco)')}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          Fonte de preço: <span className="font-mono">{searchStats.price_source || (searchStats.enable_price_mismatch ? 'site' : 'google')}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Validation Failures Table */}
                {searchStats.validation_failures && searchStats.validation_failures.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      ❌ Produtos que Falharam ({searchStats.validation_failures.length}):
                    </p>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead className="bg-gray-100 dark:bg-gray-700">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">#</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Produto</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Fonte</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Preço Google</th>
                            <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                            <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Detalhes</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                          {searchStats.validation_failures.map((failure: any, idx: number) => {
                            const isExpanded = expandedFailures.has(idx)
                            const stepLabels: Record<string, string> = {
                              'IMMERSIVE_API': 'Immersive API',
                              'URL_VALIDATION': 'Validação URL',
                              'PRICE_EXTRACTION': 'Extração Preço',
                              'PRICE_VALIDATION': 'Validação Preço',
                              'SCREENSHOT_CAPTURE': 'Captura Screenshot',
                              'PAGE_LOAD': 'Carregamento Página',
                              'UNKNOWN': 'Desconhecido'
                            }
                            return (
                              <>
                                <tr key={idx} className={isExpanded ? 'bg-red-50 dark:bg-red-900/20' : ''}>
                                  <td className="px-3 py-2 text-sm text-gray-900 dark:text-gray-100">#{idx + 1}</td>
                                  <td className="px-3 py-2 text-sm text-gray-900 dark:text-gray-100 max-w-xs truncate" title={failure.title}>
                                    {failure.title?.substring(0, 50)}...
                                  </td>
                                  <td className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">{failure.source}</td>
                                  <td className="px-3 py-2 text-sm text-right text-gray-900 dark:text-gray-100">
                                    {failure.google_price ? `R$ ${failure.google_price.toFixed(2)}` : '-'}
                                  </td>
                                  <td className="px-3 py-2 text-sm text-center">
                                    <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                                      ✗ Inválido
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-sm text-center">
                                    <button
                                      onClick={() => {
                                        const newSet = new Set(expandedFailures)
                                        if (isExpanded) {
                                          newSet.delete(idx)
                                        } else {
                                          newSet.add(idx)
                                        }
                                        setExpandedFailures(newSet)
                                      }}
                                      className="text-primary-600 hover:text-primary-800 dark:text-primary-400 underline"
                                    >
                                      {isExpanded ? 'ocultar' : 'ver'}
                                    </button>
                                  </td>
                                </tr>
                                {isExpanded && (
                                  <tr key={`${idx}-detail`} className="bg-red-50 dark:bg-red-900/20">
                                    <td colSpan={6} className="px-3 py-3">
                                      <div className="space-y-2 text-sm">
                                        <div className="flex items-center gap-2">
                                          <span className="font-medium text-gray-700 dark:text-gray-300">Etapa da Falha:</span>
                                          <span className="px-2 py-1 text-xs rounded bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200">
                                            {stepLabels[failure.failure_step] || failure.failure_step}
                                          </span>
                                        </div>
                                        {failure.domain && (
                                          <div>
                                            <span className="font-medium text-gray-700 dark:text-gray-300">Domínio:</span>{' '}
                                            <span className="text-gray-600 dark:text-gray-400">{failure.domain}</span>
                                          </div>
                                        )}
                                        {failure.url && (
                                          <div>
                                            <span className="font-medium text-gray-700 dark:text-gray-300">URL:</span>{' '}
                                            <a href={failure.url} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline break-all">
                                              {failure.url.substring(0, 80)}...
                                            </a>
                                          </div>
                                        )}
                                        <div>
                                          <span className="font-medium text-gray-700 dark:text-gray-300">Erro:</span>{' '}
                                          <span className="text-red-600 dark:text-red-400 font-mono text-xs">{failure.error_message}</span>
                                        </div>
                                      </div>
                                    </td>
                                  </tr>
                                )}
                              </>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Successful Products */}
                {searchStats.successful_products && searchStats.successful_products.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      ✓ Produtos com Sucesso ({searchStats.successful_products.length}):
                    </p>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead className="bg-gray-100 dark:bg-gray-700">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">#</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Produto</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Domínio</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Preço Google</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Preço Extraído</th>
                            <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                          {searchStats.successful_products.map((product: any, idx: number) => (
                            <tr key={idx}>
                              <td className="px-3 py-2 text-sm text-gray-900 dark:text-gray-100">#{idx + 1}</td>
                              <td className="px-3 py-2 text-sm text-gray-900 dark:text-gray-100 max-w-xs truncate" title={product.title}>
                                {product.title?.substring(0, 50)}...
                              </td>
                              <td className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">{product.domain}</td>
                              <td className="px-3 py-2 text-sm text-right text-gray-900 dark:text-gray-100">
                                {product.google_price ? `R$ ${product.google_price.toFixed(2)}` : '-'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right font-medium text-green-600 dark:text-green-400">
                                R$ {product.extracted_price?.toFixed(2)}
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                  ✓ OK
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Histórico Cronológico de Blocos */}
                {(searchStats.initial_products_sorted?.length > 0 || searchStats.block_history?.length > 0) && (
                  <div className="mt-4 border-t border-gray-300 dark:border-gray-600 pt-4">
                    <details className="group">
                      <summary className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 cursor-pointer list-none flex items-center gap-2">
                        <svg className="w-4 h-4 transform group-open:rotate-90 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                        📊 Histórico de Blocos ({searchStats.block_history?.length || 0} blocos criados)
                      </summary>

                      <div className="mt-3 space-y-4">
                        {/* 1. Lista inicial de produtos ordenados por preço */}
                        {searchStats.initial_products_sorted && searchStats.initial_products_sorted.length > 0 && (
                          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 border border-blue-200 dark:border-blue-800">
                            <h4 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
                              📋 Lista Inicial de Produtos (ordenados por preço crescente)
                            </h4>
                            <div className="max-h-48 overflow-y-auto">
                              <table className="w-full text-xs">
                                <thead className="bg-blue-100 dark:bg-blue-900/40 sticky top-0">
                                  <tr>
                                    <th className="px-2 py-1 text-left text-blue-700 dark:text-blue-300">#</th>
                                    <th className="px-2 py-1 text-left text-blue-700 dark:text-blue-300">Produto</th>
                                    <th className="px-2 py-1 text-left text-blue-700 dark:text-blue-300">Fonte</th>
                                    <th className="px-2 py-1 text-right text-blue-700 dark:text-blue-300">Preço</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {searchStats.initial_products_sorted.map((p: any) => (
                                    <tr key={p.index} className="border-b border-blue-100 dark:border-blue-800/50 hover:bg-blue-100/50 dark:hover:bg-blue-900/30">
                                      <td className="px-2 py-1 font-mono text-blue-600 dark:text-blue-400">{p.index}</td>
                                      <td className="px-2 py-1 truncate max-w-[200px]" title={p.title}>{p.title}</td>
                                      <td className="px-2 py-1 text-gray-600 dark:text-gray-400">{p.source}</td>
                                      <td className="px-2 py-1 text-right font-mono">R$ {p.price?.toFixed(2)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {/* 2. Blocos criados cronologicamente */}
                        {searchStats.block_history && searchStats.block_history.map((block: any, blockIdx: number) => (
                          <div key={blockIdx} className="bg-white dark:bg-gray-700 rounded-lg border-2 border-purple-300 dark:border-purple-700 overflow-hidden">
                            {/* Header da Iteração */}
                            <div className="bg-purple-100 dark:bg-purple-900/40 px-3 py-2 border-b border-purple-200 dark:border-purple-800">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="bg-purple-600 text-white text-sm font-bold px-3 py-1 rounded">
                                    Iteração #{block.iteration}
                                  </span>
                                  <span className="text-xs text-gray-600 dark:text-gray-300">
                                    {block.status_before?.valid_count || 0} válidas, faltam {block.status_before?.needed || 0}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="p-3 space-y-3">
                              {/* ETAPA 1: Produtos disponíveis para cálculo */}
                              {block.available_for_calculation && (
                                <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-2 border border-yellow-200 dark:border-yellow-800">
                                  <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-semibold text-yellow-800 dark:text-yellow-300">
                                      1️⃣ Produtos disponíveis para cálculo de blocos
                                    </span>
                                    <div className="flex items-center gap-2 text-[10px]">
                                      <span className="text-yellow-700 dark:text-yellow-400">
                                        {block.available_for_calculation.count} produtos
                                      </span>
                                      {block.available_for_calculation.discarded_failures > 0 && (
                                        <span className="text-red-600 dark:text-red-400">
                                          ({block.available_for_calculation.discarded_failures} descartados por falha)
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <details className="group">
                                    <summary className="text-[10px] text-yellow-700 dark:text-yellow-400 cursor-pointer">
                                      Ver lista de produtos [{block.available_for_calculation.indices?.join(', ')}]
                                    </summary>
                                    <div className="mt-1 flex flex-wrap gap-1 max-h-32 overflow-y-auto">
                                      {block.available_for_calculation.products?.map((p: any, pIdx: number) => (
                                        <span
                                          key={pIdx}
                                          className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${
                                            p.status === 'validated'
                                              ? 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300'
                                              : 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-300'
                                          }`}
                                          title={`${p.title} - ${p.source} - R$ ${p.price?.toFixed(2)}`}
                                        >
                                          {p.status === 'validated' && <span>✓</span>}
                                          <span className="font-mono">#{p.index}</span>
                                          <span>R$ {p.price?.toFixed(2)}</span>
                                        </span>
                                      ))}
                                    </div>
                                  </details>
                                </div>
                              )}

                              {/* ETAPA 2: Bloco selecionado */}
                              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-2 border border-blue-200 dark:border-blue-800">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs font-semibold text-blue-800 dark:text-blue-300">
                                    2️⃣ Bloco selecionado: [{block.products_indices?.join(', ')}]
                                  </span>
                                  <div className="flex items-center gap-2 text-[10px]">
                                    <span className="px-2 py-0.5 bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200 rounded">
                                      {block.block_size || block.products_in_block?.length} produtos
                                    </span>
                                    <span className="text-blue-600 dark:text-blue-400">
                                      R$ {block.price_range?.min?.toFixed(2)} - R$ {block.price_range?.max?.toFixed(2)}
                                    </span>
                                  </div>
                                </div>
                                {block.selection_criteria && (
                                  <div className="text-[10px] text-blue-600 dark:text-blue-400 italic mb-2">
                                    {block.selection_criteria}
                                  </div>
                                )}
                                <div className="flex flex-wrap gap-1">
                                  {block.products_in_block?.map((p: any, pIdx: number) => (
                                    <span
                                      key={pIdx}
                                      className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border ${
                                        p.status === 'validated'
                                          ? 'bg-green-100 dark:bg-green-900/40 border-green-300 dark:border-green-700 text-green-800 dark:text-green-300'
                                          : 'bg-white dark:bg-gray-600 border-blue-200 dark:border-blue-700'
                                      }`}
                                      title={`${p.title} - ${p.source} - R$ ${p.price?.toFixed(2)}`}
                                    >
                                      {p.status === 'validated' && <span className="text-green-600">✓</span>}
                                      <span className="font-mono text-blue-600 dark:text-blue-400">#{p.index}</span>
                                      <span className="truncate max-w-[80px]">{p.title?.substring(0, 15)}...</span>
                                      <span className="text-gray-500">R$ {p.price?.toFixed(2)}</span>
                                    </span>
                                  ))}
                                </div>
                                <div className="mt-1 flex gap-3 text-[10px] text-gray-400">
                                  {block.validated_in_block > 0 && (
                                    <span><span className="inline-block w-2 h-2 bg-green-500 rounded mr-1"></span>{block.validated_in_block} já validado(s)</span>
                                  )}
                                  {block.untried_count > 0 && (
                                    <span><span className="inline-block w-2 h-2 bg-blue-400 rounded mr-1"></span>{block.untried_count} a testar</span>
                                  )}
                                </div>
                              </div>

                              {/* ETAPA 3: Testes realizados */}
                              {block.tests && block.tests.length > 0 && (
                                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2 border border-gray-200 dark:border-gray-600">
                                  <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 block">
                                    3️⃣ Testes realizados ({block.tests.length})
                                  </span>
                                  <div className="space-y-1">
                                    {block.tests.map((test: any, testIdx: number) => (
                                      <div key={testIdx} className={`text-xs p-2 rounded ${test.result === 'success' ? 'bg-green-100 dark:bg-green-900/30 border-l-3 border-green-500' : 'bg-red-100 dark:bg-red-900/30 border-l-3 border-red-500'}`}>
                                        <div className="flex items-center justify-between">
                                          <div className="flex items-center gap-2">
                                            <span className="font-mono text-purple-600 dark:text-purple-400 font-bold">#{test.product_index}</span>
                                            <span className="truncate max-w-[180px]" title={test.title}>{test.title}</span>
                                          </div>
                                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${test.result === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`}>
                                            {test.result === 'success' ? '✓ VÁLIDO' : '✗ FALHA'}
                                          </span>
                                        </div>
                                        <div className="text-gray-600 dark:text-gray-400 mt-1 text-[11px]">
                                          {test.source} | Google: R$ {test.google_price?.toFixed(2)}
                                          {test.result === 'success' && (
                                            <span className="text-green-700 dark:text-green-400 ml-2">
                                              → Extraído: R$ {test.extracted_price?.toFixed(2)} ({test.domain})
                                            </span>
                                          )}
                                          {test.result === 'failed' && (
                                            <span className="text-red-700 dark:text-red-400 ml-2">
                                              → {test.failure_step}: {test.error_message?.substring(0, 60)}
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Resultado da iteração */}
                              {block.status_after && (
                                <div className="bg-gray-100 dark:bg-gray-600 rounded-lg p-2 flex items-center justify-between text-xs">
                                  <span className="text-gray-600 dark:text-gray-300">
                                    Resultado: <span className="text-green-600 dark:text-green-400 font-medium">{block.status_after.successes_this_block} sucesso(s)</span>,{' '}
                                    <span className="text-red-600 dark:text-red-400 font-medium">{block.status_after.failures_this_block} falha(s)</span>
                                  </span>
                                  <span className="font-bold text-purple-700 dark:text-purple-300">
                                    Total válidas: {block.status_after.valid_count}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}

                        {/* Caso não tenha block_history mas tenha block_iterations (dados antigos) */}
                        {(!searchStats.block_history || searchStats.block_history.length === 0) && searchStats.block_iterations && searchStats.block_iterations.length > 0 && (
                          <div className="text-xs text-gray-500 dark:text-gray-400 italic">
                            Dados de blocos no formato antigo ({searchStats.block_iterations.length} iterações). Execute uma nova cotação para ver o formato atualizado.
                          </div>
                        )}
                      </div>
                    </details>
                  </div>
                )}
              </div>
            )
          })()}
        </div>
      )}

      {/* Modal de Visualização do Prompt */}
      {showPromptModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Prompt Enviado para IA
              </h3>
              <button
                onClick={() => {
                  setShowPromptModal(false)
                  setSelectedPrompt(null)
                }}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 overflow-auto flex-1">
              <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-4 rounded-lg font-mono">
                {selectedPrompt || 'Nenhum prompt disponível'}
              </pre>
            </div>
            <div className="flex justify-end p-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => {
                  setShowPromptModal(false)
                  setSelectedPrompt(null)
                }}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Vinculação de Material */}
      {showMaterialModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  Vincular Material e Características
                </h2>
                <button
                  onClick={handleCloseMaterialModal}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-6">
                {/* Especificações Detectadas */}
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                    Especificações Detectadas na Imagem:
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {quote.claude_payload_json?.especificacoes_tecnicas &&
                      Object.entries(quote.claude_payload_json.especificacoes_tecnicas).map(([key, value]) => (
                        <div key={key} className="text-sm">
                          <span className="font-medium text-gray-700 dark:text-gray-300">{key}:</span>{' '}
                          <span className="text-gray-600 dark:text-gray-400">{String(value)}</span>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Sugestão de Vinculação */}
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                    Materiais Sugeridos:
                  </h3>

                  {loadingSuggestions && (
                    <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 text-center">
                      <div className="flex items-center justify-center">
                        <svg className="animate-spin h-6 w-6 mr-3 text-blue-600" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span className="text-gray-600 dark:text-gray-400">Buscando materiais compatíveis...</span>
                      </div>
                    </div>
                  )}

                  {!loadingSuggestions && suggestions.length === 0 && (
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 text-center">
                      <p className="text-gray-700 dark:text-gray-300">
                        Nenhum material similar encontrado na base de dados.
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        Considere criar um novo material abaixo.
                      </p>
                    </div>
                  )}

                  {!loadingSuggestions && suggestions.length > 0 && (
                    <div className="space-y-3">
                      {suggestions.map((material) => (
                        <div
                          key={material.id}
                          onClick={() => handleSelectMaterial(material.id)}
                          className={`border rounded-lg p-4 cursor-pointer transition-all ${
                            selectedMaterialId === material.id
                              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                              : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700'
                          }`}
                        >
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                  {material.nome}
                                </h4>
                                <span className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 text-xs font-medium rounded">
                                  {material.similarity_score.toFixed(0)}% match
                                </span>
                              </div>
                              {material.codigo && (
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  Código: {material.codigo}
                                </p>
                              )}
                              {material.descricao && (
                                <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
                                  {material.descricao}
                                </p>
                              )}
                            </div>
                          </div>

                          {material.matched_specs.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                              <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Especificações correspondentes:
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {material.matched_specs.map((spec, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded"
                                  >
                                    {spec}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {material.caracteristicas.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                              <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Características do material:
                              </p>
                              <div className="text-xs text-gray-600 dark:text-gray-400">
                                {material.caracteristicas.map((char) => char.nome).join(', ')}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Opção de Criar Novo Material */}
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <button className="btn-secondary w-full">
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Criar Novo Material
                  </button>
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  onClick={handleCloseMaterialModal}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!selectedMaterialId}
                  onClick={handleConfirmLinkMaterial}
                >
                  Vincular Material Selecionado
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
