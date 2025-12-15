'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { batchQuotesApi, BatchListItem } from '@/lib/api'

export default function BatchHistoryPage() {
  const [batches, setBatches] = useState<BatchListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')

  useEffect(() => {
    loadBatches()
  }, [page, statusFilter])

  const loadBatches = async () => {
    setLoading(true)
    try {
      const response = await batchQuotesApi.listBatches(page, 20, undefined, statusFilter || undefined)
      setBatches(response.items)
      setTotalPages(Math.ceil(response.total / 20))
    } catch (error) {
      console.error('Erro ao carregar lotes:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
      PENDING: { bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-800 dark:text-gray-200', label: 'Pendente' },
      PROCESSING: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-800 dark:text-blue-200', label: 'Processando' },
      COMPLETED: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-200', label: 'Concluido' },
      PARTIALLY_COMPLETED: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-800 dark:text-yellow-200', label: 'Parcial' },
      ERROR: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-800 dark:text-red-200', label: 'Erro' },
      CANCELLED: { bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-800 dark:text-gray-200', label: 'Cancelado' },
    }
    const config = statusConfig[status] || statusConfig.PENDING
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    )
  }

  const getInputTypeBadge = (inputType: string) => {
    const typeConfig: Record<string, { bg: string; text: string; label: string }> = {
      TEXT_BATCH: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-800 dark:text-purple-200', label: 'Texto' },
      IMAGE_BATCH: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-800 dark:text-indigo-200', label: 'Imagens' },
      FILE_BATCH: { bg: 'bg-cyan-100 dark:bg-cyan-900/30', text: 'text-cyan-800 dark:text-cyan-200', label: 'Arquivo' },
    }
    const config = typeConfig[inputType] || typeConfig.TEXT_BATCH
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    )
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

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Historico de Lotes
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Visualize todos os lotes de cotacao processados
        </p>
      </div>

      {/* Filtros */}
      <div className="mb-6 flex gap-4 items-center">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Filtrar por Status
          </label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Todos</option>
            <option value="COMPLETED">Concluidos</option>
            <option value="PARTIALLY_COMPLETED">Parciais</option>
            <option value="PROCESSING">Processando</option>
            <option value="ERROR">Com Erro</option>
            <option value="CANCELLED">Cancelados</option>
          </select>
        </div>
        <div className="flex-1" />
        <Link
          href="/cotacao/lote"
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          + Novo Lote
        </Link>
      </div>

      {/* Tabela */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
            <p className="mt-2 text-gray-600 dark:text-gray-400">Carregando...</p>
          </div>
        ) : batches.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-gray-600 dark:text-gray-400">Nenhum lote encontrado</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Tipo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Projeto</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Itens</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Progresso</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Data</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Acoes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {batches.map((batch) => (
                <tr key={batch.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                    #{batch.id}
                  </td>
                  <td className="px-4 py-3">
                    {getInputTypeBadge(batch.input_type)}
                  </td>
                  <td className="px-4 py-3">
                    {getStatusBadge(batch.status)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                    {batch.project_nome || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-center text-gray-600 dark:text-gray-400">
                    {batch.completed_items}/{batch.total_items}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2 w-20">
                        <div
                          className="bg-primary-600 h-2 rounded-full transition-all"
                          style={{ width: `${batch.progress_percentage}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-600 dark:text-gray-400">
                        {batch.progress_percentage.toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                    {formatDate(batch.created_at)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Link
                      href={`/cotacao/lote/${batch.id}`}
                      className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                    >
                      Ver Detalhes
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Paginacao */}
      {totalPages > 1 && (
        <div className="mt-4 flex justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Anterior
          </button>
          <span className="px-3 py-1 text-gray-600 dark:text-gray-400">
            Pagina {page} de {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Proxima
          </button>
        </div>
      )}
    </div>
  )
}
