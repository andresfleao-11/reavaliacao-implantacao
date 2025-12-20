'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { batchQuotesApi, BatchJob, BatchQuoteItem, BatchCosts } from '@/lib/api'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import Link from 'next/link'

const STATUS_COLORS: Record<string, string> = {
  'PENDING': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  'PROCESSING': 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300',
  'COMPLETED': 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300',
  'PARTIALLY_COMPLETED': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300',
  'ERROR': 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300',
  'CANCELLED': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  'DONE': 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300',
  'AWAITING_REVIEW': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300',
}

const STATUS_LABELS: Record<string, string> = {
  'PENDING': 'Pendente',
  'PROCESSING': 'Processando',
  'COMPLETED': 'Concluido',
  'PARTIALLY_COMPLETED': 'Parcialmente Concluido',
  'ERROR': 'Erro',
  'CANCELLED': 'Cancelado',
  'DONE': 'Concluido',
  'AWAITING_REVIEW': 'Aguardando Revisao',
}

const INPUT_TYPE_LABELS: Record<string, string> = {
  'TEXT_BATCH': 'Texto',
  'IMAGE_BATCH': 'Imagens',
  'FILE_BATCH': 'Arquivo',
}

export default function BatchDetailPage() {
  const params = useParams()
  const router = useRouter()
  const batchId = parseInt(params.id as string)

  const [batch, setBatch] = useState<BatchJob | null>(null)
  const [quotes, setQuotes] = useState<BatchQuoteItem[]>([])
  const [costs, setCosts] = useState<BatchCosts | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const [totalQuotes, setTotalQuotes] = useState(0)
  const [actionLoading, setActionLoading] = useState(false)

  const perPage = 20

  // Carregar dados do lote
  const loadBatch = async () => {
    try {
      const data = await batchQuotesApi.getBatch(batchId)
      setBatch(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao carregar lote')
    }
  }

  // Carregar cotacoes do lote
  const loadQuotes = async () => {
    try {
      const data = await batchQuotesApi.getBatchQuotes(batchId, page, perPage, statusFilter || undefined)
      setQuotes(data.items)
      setTotalQuotes(data.total)
    } catch (err: any) {
      console.error('Error loading quotes:', err)
    }
  }

  // Carregar custos do lote
  const loadCosts = async () => {
    try {
      const data = await batchQuotesApi.getBatchCosts(batchId)
      setCosts(data)
    } catch (err: any) {
      console.error('Error loading costs:', err)
    }
  }

  // Carregar dados iniciais
  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await loadBatch()
      await loadQuotes()
      await loadCosts()
      setLoading(false)
    }
    loadData()
  }, [batchId])

  // Recarregar quando filtro ou pagina mudar
  useEffect(() => {
    if (!loading) {
      loadQuotes()
    }
  }, [statusFilter, page])

  // Polling para atualizar status durante processamento
  useEffect(() => {
    if (batch?.status === 'PROCESSING' || batch?.status === 'PENDING') {
      const interval = setInterval(() => {
        loadBatch()
        loadQuotes()
      }, 3000)
      return () => clearInterval(interval)
    }
  }, [batch?.status])

  const handleCancel = async () => {
    if (!confirm('Tem certeza que deseja cancelar este lote?')) return

    setActionLoading(true)
    try {
      await batchQuotesApi.cancelBatch(batchId)
      await loadBatch()
      await loadQuotes()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao cancelar lote')
    } finally {
      setActionLoading(false)
    }
  }

  const handleResume = async () => {
    setActionLoading(true)
    try {
      await batchQuotesApi.resumeBatch(batchId)
      await loadBatch()
      await loadQuotes()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao retomar lote')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6 flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-12 w-12 mx-auto text-blue-500" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="mt-4 text-gray-500 dark:text-gray-400">Carregando...</p>
        </div>
      </div>
    )
  }

  if (!batch) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-2xl font-bold text-red-600">Lote não encontrado</h1>
          <button
            onClick={() => router.push('/cotacao/lote')}
            className="mt-4 text-blue-600 hover:underline"
          >
            Voltar para Cotação em Lote
          </button>
        </div>
      </div>
    )
  }

  const totalPages = Math.ceil(totalQuotes / perPage)

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-3 sm:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 sm:mb-6">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
              Lote #{batch.id}
            </h1>
            <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mt-1">
              {format(new Date(batch.created_at), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
            </p>
          </div>
          <div className="flex gap-2">
            {batch.can_resume && (
              <button
                onClick={handleResume}
                disabled={actionLoading}
                className="flex-1 sm:flex-none px-3 sm:px-4 py-1.5 sm:py-2 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium disabled:opacity-50"
              >
                Retomar
              </button>
            )}
            {(batch.status === 'PROCESSING' || batch.status === 'PENDING') && (
              <button
                onClick={handleCancel}
                disabled={actionLoading}
                className="flex-1 sm:flex-none px-3 sm:px-4 py-1.5 sm:py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium disabled:opacity-50"
              >
                Cancelar
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Status e Progresso */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6 mb-4 sm:mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-4 mb-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-medium ${STATUS_COLORS[batch.status]}`}>
                {STATUS_LABELS[batch.status] || batch.status}
              </span>
              <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                {INPUT_TYPE_LABELS[batch.input_type] || batch.input_type}
              </span>
            </div>
            {batch.project && (
              <span className="text-xs sm:text-sm text-gray-600 dark:text-gray-300">
                {batch.project.nome}
              </span>
            )}
          </div>

          {/* Barra de Progresso */}
          <div className="mb-4">
            <div className="flex justify-between text-xs sm:text-sm mb-1">
              <span className="text-gray-600 dark:text-gray-300">Progresso</span>
              <span className="text-gray-900 dark:text-white font-medium">
                {batch.progress_percentage.toFixed(0)}%
              </span>
            </div>
            <div className="h-2 sm:h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${batch.progress_percentage}%` }}
              />
            </div>
          </div>

          {/* Contadores */}
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-4">
            <div className="text-center p-2 sm:p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-lg sm:text-2xl font-bold text-gray-900 dark:text-white">
                {batch.total_items}
              </div>
              <div className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Total</div>
            </div>
            <div className="text-center p-2 sm:p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">
              <div className="text-lg sm:text-2xl font-bold text-green-600 dark:text-green-400">
                {batch.quotes_done}
              </div>
              <div className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">OK</div>
            </div>
            <div className="text-center p-2 sm:p-3 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg">
              <div className="text-lg sm:text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                {batch.quotes_awaiting_review}
              </div>
              <div className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Revisão</div>
            </div>
            <div className="text-center p-2 sm:p-3 bg-red-50 dark:bg-red-900/30 rounded-lg">
              <div className="text-lg sm:text-2xl font-bold text-red-600 dark:text-red-400">
                {batch.failed_items}
              </div>
              <div className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Falhas</div>
            </div>
            <div className="text-center p-2 sm:p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg col-span-3 sm:col-span-1">
              <div className="text-lg sm:text-2xl font-bold text-blue-600 dark:text-blue-400">
                {batch.total_items - batch.completed_items - batch.failed_items}
              </div>
              <div className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400">Pendentes</div>
            </div>
          </div>

          {batch.error_message && (
            <div className="mt-3 sm:mt-4 p-2 sm:p-3 bg-red-50 dark:bg-red-900/30 rounded-lg text-xs sm:text-sm text-red-700 dark:text-red-300">
              {batch.error_message}
            </div>
          )}
        </div>

        {/* Botões de Download - quando lote finalizado */}
        {(batch.status === 'COMPLETED' || batch.status === 'PARTIALLY_COMPLETED') && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6 mb-4 sm:mb-6">
            <h2 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
              Arquivos de Resultado
            </h2>
            <div className="flex flex-wrap gap-3">
              <a
                href={batchQuotesApi.getDownloadZipUrl(batchId)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors text-sm"
                download
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Baixar PDFs (ZIP)
              </a>
              <a
                href={batchQuotesApi.getDownloadExcelUrl(batchId)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors text-sm"
                download
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Baixar Resumo (Excel)
              </a>
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              O ZIP contém todos os PDFs das cotações. O Excel contém o resumo com valores de cada cotação.
            </p>
          </div>
        )}

        {/* Resumo de Custos */}
        {costs && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 sm:p-6 mb-4 sm:mb-6">
            <h2 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
              Custos de API
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-6">
              {/* Anthropic */}
              <div className="p-3 sm:p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <div className="flex items-center gap-2 mb-2 sm:mb-3">
                  <span className="text-xs sm:text-sm font-medium text-purple-900 dark:text-purple-200">Anthropic</span>
                </div>
                <div className="space-y-1 sm:space-y-2 text-xs sm:text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Chamadas:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.anthropic.calls}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Tokens:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.anthropic.total_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between pt-1 sm:pt-2 border-t border-purple-200 dark:border-purple-700">
                    <span className="text-gray-600 dark:text-gray-400">Custo:</span>
                    <span className="font-medium text-purple-600 dark:text-purple-400">US$ {costs.anthropic.cost_usd.toFixed(4)}</span>
                  </div>
                </div>
              </div>

              {/* SerpAPI */}
              <div className="p-3 sm:p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="flex items-center gap-2 mb-2 sm:mb-3">
                  <span className="text-xs sm:text-sm font-medium text-blue-900 dark:text-blue-200">SerpAPI</span>
                </div>
                <div className="space-y-1 sm:space-y-2 text-xs sm:text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Chamadas:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.serpapi.calls}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Shopping:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.serpapi.google_shopping}</span>
                  </div>
                  <div className="flex justify-between pt-1 sm:pt-2 border-t border-blue-200 dark:border-blue-700">
                    <span className="text-gray-600 dark:text-gray-400">Custo:</span>
                    <span className="font-medium text-blue-600 dark:text-blue-400">US$ {(costs.serpapi.cost_usd || 0).toFixed(4)}</span>
                  </div>
                </div>
              </div>

              {/* Total */}
              <div className="p-3 sm:p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="flex items-center gap-2 mb-2 sm:mb-3">
                  <span className="text-xs sm:text-sm font-medium text-green-900 dark:text-green-200">Total</span>
                </div>
                <div>
                  <div className="text-xl sm:text-3xl font-bold text-green-600 dark:text-green-400">
                    R$ {costs.total_cost_brl.toFixed(2)}
                  </div>
                  <div className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                    US$ {costs.total_cost_usd.toFixed(4)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Lista de Cotacoes */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-3 sm:p-4 border-b border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0">
            <h2 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-white">
              Cotações ({totalQuotes})
            </h2>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
              className="px-2 sm:px-3 py-1.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs sm:text-sm"
            >
              <option value="">Todos</option>
              <option value="PROCESSING">Processando</option>
              <option value="DONE">Concluído</option>
              <option value="AWAITING_REVIEW">Revisão</option>
              <option value="ERROR">Erro</option>
              <option value="CANCELLED">Cancelado</option>
            </select>
          </div>

          {/* Desktop Table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">#</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">ID</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Produto</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Valor</th>
                  <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Status</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {quotes.map((quote) => (
                  <tr key={quote.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {(quote.batch_index ?? 0) + 1}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-900 dark:text-white">
                      {quote.id}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-900 dark:text-white max-w-[200px] truncate">
                      {quote.nome_item || quote.codigo_item || '-'}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-900 dark:text-white text-right font-medium">
                      {quote.valor_medio ? `R$ ${quote.valor_medio.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '-'}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[quote.status]}`}>
                        {STATUS_LABELS[quote.status] || quote.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <Link href={`/cotacao/${quote.id}`} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 text-sm">
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))}
                {quotes.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                      Nenhuma cotação encontrada
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="sm:hidden divide-y divide-gray-200 dark:divide-gray-700">
            {quotes.map((quote) => (
              <Link
                key={quote.id}
                href={`/cotacao/${quote.id}`}
                className="block p-3 hover:bg-gray-50 dark:hover:bg-gray-700/50"
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 dark:text-gray-400">#{(quote.batch_index ?? 0) + 1}</span>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">ID {quote.id}</span>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[quote.status]}`}>
                    {STATUS_LABELS[quote.status] || quote.status}
                  </span>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-300 truncate mb-1">
                  {quote.nome_item || quote.codigo_item || '-'}
                </div>
                <div className="text-sm font-bold text-primary-600 dark:text-primary-400">
                  {quote.valor_medio ? `R$ ${quote.valor_medio.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '-'}
                </div>
              </Link>
            ))}
            {quotes.length === 0 && (
              <div className="p-6 text-center text-sm text-gray-500 dark:text-gray-400">
                Nenhuma cotação encontrada
              </div>
            )}
          </div>

          {/* Paginação */}
          {totalPages > 1 && (
            <div className="p-3 sm:p-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                {page}/{totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-2 sm:px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-xs sm:text-sm disabled:opacity-50"
                >
                  Anterior
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-2 sm:px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-xs sm:text-sm disabled:opacity-50"
                >
                  Próximo
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
