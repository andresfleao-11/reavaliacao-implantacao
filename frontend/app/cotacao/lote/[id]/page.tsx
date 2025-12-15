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
          <h1 className="text-2xl font-bold text-red-600">Lote nao encontrado</h1>
          <button
            onClick={() => router.push('/cotacao/lote')}
            className="mt-4 text-blue-600 hover:underline"
          >
            Voltar para Cotacao em Lote
          </button>
        </div>
      </div>
    )
  }

  const totalPages = Math.ceil(totalQuotes / perPage)

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Lote #{batch.id}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Criado em {format(new Date(batch.created_at), "dd/MM/yyyy 'as' HH:mm", { locale: ptBR })}
            </p>
          </div>
          <div className="flex gap-2">
            {batch.can_resume && (
              <button
                onClick={handleResume}
                disabled={actionLoading}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium disabled:opacity-50"
              >
                Retomar
              </button>
            )}
            {(batch.status === 'PROCESSING' || batch.status === 'PENDING') && (
              <button
                onClick={handleCancel}
                disabled={actionLoading}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium disabled:opacity-50"
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
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[batch.status]}`}>
                {STATUS_LABELS[batch.status] || batch.status}
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {INPUT_TYPE_LABELS[batch.input_type] || batch.input_type}
              </span>
            </div>
            {batch.project && (
              <span className="text-sm text-gray-600 dark:text-gray-300">
                Projeto: {batch.project.nome}
              </span>
            )}
          </div>

          {/* Barra de Progresso */}
          <div className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600 dark:text-gray-300">Progresso</span>
              <span className="text-gray-900 dark:text-white font-medium">
                {batch.progress_percentage.toFixed(0)}%
              </span>
            </div>
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${batch.progress_percentage}%` }}
              />
            </div>
          </div>

          {/* Contadores */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {batch.total_items}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Total</div>
            </div>
            <div className="text-center p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {batch.quotes_done}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Concluidas</div>
            </div>
            <div className="text-center p-3 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                {batch.quotes_awaiting_review}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Aguardando Revisao</div>
            </div>
            <div className="text-center p-3 bg-red-50 dark:bg-red-900/30 rounded-lg">
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                {batch.failed_items}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Falhas</div>
            </div>
            <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {batch.total_items - batch.completed_items - batch.failed_items}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Pendentes</div>
            </div>
          </div>

          {batch.error_message && (
            <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/30 rounded-lg text-sm text-red-700 dark:text-red-300">
              {batch.error_message}
            </div>
          )}
        </div>

        {/* Resumo de Custos */}
        {costs && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Resumo de Custos e Chamadas de API
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Anthropic */}
              <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <svg className="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  <span className="font-medium text-purple-900 dark:text-purple-200">Anthropic (IA)</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Chamadas:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.anthropic.calls}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Tokens (entrada):</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.anthropic.input_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Tokens (saida):</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.anthropic.output_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Tokens total:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.anthropic.total_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between pt-2 border-t border-purple-200 dark:border-purple-700">
                    <span className="text-gray-600 dark:text-gray-400">Custo:</span>
                    <span className="font-medium text-purple-600 dark:text-purple-400">US$ {costs.anthropic.cost_usd.toFixed(4)}</span>
                  </div>
                </div>
              </div>

              {/* SerpAPI */}
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <span className="font-medium text-blue-900 dark:text-blue-200">SerpAPI (Buscas)</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Total de chamadas:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.serpapi.calls}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Google Shopping:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.serpapi.google_shopping}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Immersive Product:</span>
                    <span className="font-medium text-gray-900 dark:text-white">{costs.serpapi.immersive_product}</span>
                  </div>
                  <div className="flex justify-between pt-2 border-t border-blue-200 dark:border-blue-700">
                    <span className="text-gray-600 dark:text-gray-400">Custo estimado:</span>
                    <span className="font-medium text-blue-600 dark:text-blue-400">US$ {(costs.serpapi.cost_usd || 0).toFixed(4)}</span>
                  </div>
                </div>
              </div>

              {/* Total */}
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-medium text-green-900 dark:text-green-200">Custo Total</span>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                      R$ {costs.total_cost_brl.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      US$ {costs.total_cost_usd.toFixed(4)}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-green-200 dark:border-green-700">
                    * Custo SerpAPI estimado em US$ 0.005/chamada
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Lista de Cotacoes */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Cotacoes ({totalQuotes})
            </h2>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
            >
              <option value="">Todos os status</option>
              <option value="PROCESSING">Processando</option>
              <option value="DONE">Concluido</option>
              <option value="AWAITING_REVIEW">Aguardando Revisao</option>
              <option value="ERROR">Erro</option>
              <option value="CANCELLED">Cancelado</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">#</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Produto</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Valor Medio</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Acoes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {quotes.map((quote) => (
                  <tr key={quote.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                      {(quote.batch_index ?? 0) + 1}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                      {quote.id}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white max-w-xs truncate">
                      {quote.nome_item || quote.codigo_item || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                      {quote.valor_medio
                        ? `R$ ${quote.valor_medio.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                        : '-'
                      }
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[quote.status]}`}>
                        {STATUS_LABELS[quote.status] || quote.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/cotacao/${quote.id}`}
                        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm"
                      >
                        Ver detalhes
                      </Link>
                    </td>
                  </tr>
                ))}
                {quotes.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                      Nenhuma cotacao encontrada
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Paginacao */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Pagina {page} de {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm disabled:opacity-50"
                >
                  Anterior
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm disabled:opacity-50"
                >
                  Proximo
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
