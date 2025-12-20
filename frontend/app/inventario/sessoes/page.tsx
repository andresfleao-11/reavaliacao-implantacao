'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { inventorySessionsApi, InventorySession } from '@/lib/api'

type SessionStatus = 'draft' | 'in_progress' | 'paused' | 'completed' | 'cancelled'

export default function SessoesInventarioPage() {
  const [sessions, setSessions] = useState<InventorySession[]>([])
  const [totalSessions, setTotalSessions] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Pagination
  const [page, setPage] = useState(1)
  const [limit] = useState(10)

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('')

  useEffect(() => {
    loadSessions()
  }, [page, statusFilter])

  const loadSessions = async () => {
    try {
      setLoading(true)
      setError(null)

      const params: any = {
        skip: (page - 1) * limit,
        limit
      }

      if (statusFilter) params.status = statusFilter

      const data = await inventorySessionsApi.list(params)
      setSessions(data.items)
      setTotalSessions(data.total)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar sessões')
    } finally {
      setLoading(false)
    }
  }

  const handleStartSession = async (id: number) => {
    try {
      await inventorySessionsApi.start(id)
      loadSessions()
    } catch (err: any) {
      setError(err.message || 'Erro ao iniciar sessão')
    }
  }

  const handlePauseSession = async (id: number) => {
    try {
      await inventorySessionsApi.pause(id)
      loadSessions()
    } catch (err: any) {
      setError(err.message || 'Erro ao pausar sessão')
    }
  }

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { bg: string; text: string; label: string }> = {
      draft: { bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-700 dark:text-gray-300', label: 'Rascunho' },
      in_progress: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400', label: 'Em Andamento' },
      paused: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-700 dark:text-yellow-400', label: 'Pausada' },
      completed: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', label: 'Concluída' },
      cancelled: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', label: 'Cancelada' }
    }
    const badge = badges[status] || badges.draft
    return (
      <span className={`px-2 py-1 text-xs rounded-full ${badge.bg} ${badge.text}`}>
        {badge.label}
      </span>
    )
  }

  const getProgressBar = (session: InventorySession) => {
    const stats = session.statistics
    const total = stats?.total_expected || 0
    const found = stats?.total_found || 0
    const percentage = stats?.completion_percentage || 0

    return (
      <div className="w-full">
        <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
          <span>{found} de {total} bens</span>
          <span>{percentage.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div
            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    )
  }

  const totalPages = Math.ceil(totalSessions / limit)

  if (loading && sessions.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Sessões de Inventário</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Gerencie suas sessões de inventário patrimonial
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="">Todos</option>
              <option value="draft">Rascunho</option>
              <option value="in_progress">Em Andamento</option>
              <option value="paused">Pausada</option>
              <option value="completed">Concluída</option>
              <option value="cancelled">Cancelada</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Fechar</button>
        </div>
      )}

      {/* Sessions List */}
      {sessions.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Nenhuma sessão encontrada
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            {statusFilter
              ? 'Nenhuma sessão corresponde aos filtros aplicados.'
              : 'As sessões de inventário são criadas pelo sistema externo.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-lg transition-shadow"
            >
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Link
                        href={`/inventario/sessoes/${session.id}`}
                        className="text-lg font-semibold text-gray-900 dark:text-white hover:text-primary-600 dark:hover:text-primary-400"
                      >
                        {session.name || session.code}
                      </Link>
                      {getStatusBadge(session.status)}
                      <span className="px-2 py-1 text-xs rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                        {session.code}
                      </span>
                    </div>

                    {session.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                        {session.description}
                      </p>
                    )}

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
                      {session.project && (
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Projeto:</span>
                          <p className="font-medium text-gray-900 dark:text-white">
                            {session.project.name}
                          </p>
                        </div>
                      )}
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Criada em:</span>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {new Date(session.created_at).toLocaleDateString('pt-BR')}
                        </p>
                      </div>
                      {session.started_at && (
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Iniciada em:</span>
                          <p className="font-medium text-gray-900 dark:text-white">
                            {new Date(session.started_at).toLocaleDateString('pt-BR')}
                          </p>
                        </div>
                      )}
                      {(session.ul || session.ua) && (
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Local:</span>
                          <p className="font-medium text-gray-900 dark:text-white">
                            {session.ul?.name || session.ua?.name || '-'}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Progress Bar */}
                    <div className="max-w-md">
                      {getProgressBar(session)}
                    </div>

                    {/* Statistics */}
                    {session.statistics && (
                      <div className="flex gap-4 mt-3 text-xs">
                        <span className="text-green-600 dark:text-green-400">
                          Encontrados: {session.statistics.total_found}
                        </span>
                        <span className="text-yellow-600 dark:text-yellow-400">
                          Não encontrados: {session.statistics.total_not_found}
                        </span>
                        <span className="text-blue-600 dark:text-blue-400">
                          Não cadastrados: {session.statistics.total_unregistered}
                        </span>
                        {session.statistics.total_written_off > 0 && (
                          <span className="text-red-600 dark:text-red-400">
                            Baixados: {session.statistics.total_written_off}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    {session.status === 'draft' && (
                      <button
                        onClick={() => handleStartSession(session.id)}
                        className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors"
                      >
                        Iniciar
                      </button>
                    )}
                    {session.status === 'in_progress' && (
                      <button
                        onClick={() => handlePauseSession(session.id)}
                        className="px-3 py-1.5 bg-yellow-600 text-white text-sm rounded-lg hover:bg-yellow-700 transition-colors"
                      >
                        Pausar
                      </button>
                    )}
                    {session.status === 'paused' && (
                      <button
                        onClick={() => handleStartSession(session.id)}
                        className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        Retomar
                      </button>
                    )}
                    <Link
                      href={`/inventario/sessoes/${session.id}`}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-sm rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                      Detalhes
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Mostrando {((page - 1) * limit) + 1} a {Math.min(page * limit, totalSessions)} de {totalSessions} sessões
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50"
            >
              Anterior
            </button>
            <span className="px-3 py-1 text-gray-700 dark:text-gray-300">
              {page} de {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50"
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
