'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import useSWR from 'swr'
import { quotesApi, QuoteDetail, materialsApi, SuggestedMaterial, IntegrationLog } from '@/lib/api'
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
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
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
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
          Cotação #{quote.id}
          {quote.attempt_number > 1 && (
            <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
              (Tentativa {quote.attempt_number})
            </span>
          )}
        </h1>
        <div className="flex items-center space-x-4">
          {/* Tag de Lote */}
          {quote.batch_job_id && (
            <Link
              href={`/cotacao/lote/${quote.batch_job_id}`}
              className="px-3 py-1 rounded-full text-sm font-medium bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-200 hover:bg-cyan-200 dark:hover:bg-cyan-900/50 transition-colors"
              title="Ver lote completo"
            >
              📦 Lote #{quote.batch_job_id}
            </Link>
          )}

          {/* Tipo de Entrada */}
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${inputTypeInfo.color}`}
            title={`Tipo de entrada: ${inputTypeInfo.label}`}
          >
            {inputTypeInfo.icon} {inputTypeInfo.label}
          </span>

          {/* Status */}
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
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
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {cancelling ? 'Cancelando...' : 'Cancelar Cotação'}
            </button>
          )}

          {/* Botão de recotar para cotações canceladas ou com erro - somente se não foi recotado */}
          {(quote.status === 'CANCELLED' || quote.status === 'ERROR') && !quote.child_quote_id && (
            <button
              onClick={handleRequote}
              disabled={requoting}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {requoting ? 'Iniciando...' : 'Cotar Novamente'}
            </button>
          )}

          {/* Link para nova cotação quando já foi recotado */}
          {(quote.status === 'CANCELLED' || quote.status === 'ERROR') && quote.child_quote_id && (
            <Link
              href={`/cotacao/${quote.child_quote_id}`}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex items-center"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              Nova cotação: #{quote.child_quote_id}
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Valor Médio</h3>
          <p className="text-3xl font-bold text-primary-600 dark:text-primary-400">{formatCurrency(quote.valor_medio)}</p>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Valor Mínimo</h3>
          <p className="text-2xl font-semibold text-gray-700 dark:text-gray-300">{formatCurrency(quote.valor_minimo)}</p>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Valor Máximo</h3>
          <p className="text-2xl font-semibold text-gray-700 dark:text-gray-300">{formatCurrency(quote.valor_maximo)}</p>
        </div>
      </div>

      {/* Informações do Projeto */}
      {quote.project && (
        <div className="card mb-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Projeto Vinculado</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Projeto</p>
              <Link
                href={`/cadastros/projetos/${quote.project.id}`}
                className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 font-medium"
              >
                {quote.project.nome}
              </Link>
            </div>
            {quote.project.cliente_nome && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Cliente</p>
                <p className="text-gray-900 dark:text-gray-100">{quote.project.cliente_nome}</p>
              </div>
            )}
            {quote.project.config_versao && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Versão da Configuração</p>
                <p className="text-gray-900 dark:text-gray-100">v{quote.project.config_versao}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {quote.claude_payload_json && (
        <div className="card mb-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Análise do Item</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Nome</p>
              <p className="text-gray-900 dark:text-gray-100">{quote.claude_payload_json.nome_canonico || 'N/A'}</p>
            </div>
            {quote.claude_payload_json.marca && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Marca</p>
                <p className="text-gray-900 dark:text-gray-100">{quote.claude_payload_json.marca}</p>
              </div>
            )}
            {quote.claude_payload_json.modelo && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Modelo</p>
                <p className="text-gray-900 dark:text-gray-100">{quote.claude_payload_json.modelo}</p>
              </div>
            )}
            {quote.codigo_item && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Código</p>
                <p className="text-gray-900 dark:text-gray-100">{quote.codigo_item}</p>
              </div>
            )}
          </div>

          {/* Especificações Técnicas */}
          {quote.claude_payload_json.especificacoes_tecnicas &&
           Object.keys(quote.claude_payload_json.especificacoes_tecnicas).length > 0 && (
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Especificações Técnicas</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {Object.entries(quote.claude_payload_json.especificacoes_tecnicas).map(([key, value]) => (
                  <div key={key} className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {key.replace(/_/g, ' ')}
                    </p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
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

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Loja</th>
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
                      {source.domain || 'N/A'}
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

          {quote.sources.some((s) => s.screenshot_url) && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Evidências (Screenshots)</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {quote.sources
                  .filter((s) => s.screenshot_url)
                  .map((source) => (
                    <div key={source.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{source.domain}</p>
                      <img
                        src={`${process.env.NEXT_PUBLIC_API_URL}${source.screenshot_url}`}
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
      {quote.status === 'DONE' && quote.variacao_percentual !== null && (
        <div className="card mt-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Variação da Cotação</h2>
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
            <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-green-50 dark:from-blue-900/20 dark:to-green-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Custos desta Cotacao</h3>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Taxa: 1 USD = R$ {quoteCosts.usd_to_brl_rate.toFixed(2)}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-4">
                {/* Anthropic */}
                {quoteCosts.anthropic.calls > 0 && (
                  <div className="text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400">Anthropic ({quoteCosts.anthropic.tokens.toLocaleString()} tokens)</p>
                    <p className="text-sm font-medium text-orange-500 dark:text-orange-300">
                      $ {quoteCosts.anthropic.cost_usd.toFixed(4)} USD
                    </p>
                    <p className="text-lg font-bold text-orange-600 dark:text-orange-400">
                      R$ {quoteCosts.anthropic.cost_brl.toFixed(2)}
                    </p>
                  </div>
                )}
                {/* OpenAI */}
                {quoteCosts.openai.calls > 0 && (
                  <div className="text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400">OpenAI ({quoteCosts.openai.tokens.toLocaleString()} tokens)</p>
                    <p className="text-sm font-medium text-blue-500 dark:text-blue-300">
                      $ {quoteCosts.openai.cost_usd.toFixed(4)} USD
                    </p>
                    <p className="text-lg font-bold text-blue-600 dark:text-blue-400">
                      R$ {quoteCosts.openai.cost_brl.toFixed(2)}
                    </p>
                  </div>
                )}
                {/* SerpAPI */}
                {quoteCosts.serpapi.total_calls > 0 && (
                  <div className="text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      SerpAPI ({quoteCosts.serpapi.shopping_calls} busca + {quoteCosts.serpapi.immersive_calls} loja)
                    </p>
                    <p className="text-sm font-medium text-green-500 dark:text-green-300">
                      R$ {quoteCosts.serpapi.cost_per_call.toFixed(4)}/chamada
                    </p>
                    <p className="text-lg font-bold text-green-600 dark:text-green-400">
                      R$ {quoteCosts.serpapi.cost_brl.toFixed(2)}
                    </p>
                  </div>
                )}
                {/* Total */}
                <div className="text-center border-l border-gray-300 dark:border-gray-600 pl-4">
                  <p className="text-xs text-gray-500 dark:text-gray-400">Total</p>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    $ {quoteCosts.total_cost_usd.toFixed(4)} USD
                  </p>
                  <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                    R$ {quoteCosts.total_cost_brl.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Search Log Summary */}
          {integrationLogs.some(log => log.integration_type === 'search_log') && (
            <div className="mb-6">
              <button
                onClick={() => setSearchLogExpanded(!searchLogExpanded)}
                className="w-full flex items-center justify-between text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 hover:text-primary-600 transition-colors"
              >
                <span>📊 Log de Busca</span>
                <svg
                  className={`w-5 h-5 transform transition-transform ${searchLogExpanded ? 'rotate-180' : ''}`}
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
                    <div key={log.id} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div>
                          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Produtos Retornados</p>
                          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{summary.total_raw_products || 0}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Após Filtro Fontes</p>
                          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{summary.after_source_filter || 0}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Blocos Válidos</p>
                          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{summary.valid_blocks || 0}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Resultados Obtidos</p>
                          <p className="text-lg font-semibold text-green-600">{summary.results_obtained || 0}</p>
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
