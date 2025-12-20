'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { inventorySessionsApi, InventorySession, ExpectedAsset, SessionStatistics } from '@/lib/api'
import { ConnectionStatusIndicator } from '@/components/inventory/ConnectionStatusIndicator'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useServiceWorker } from '@/hooks/useServiceWorker'

export default function SessaoDetalhesPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = parseInt(params.id as string)

  const [session, setSession] = useState<InventorySession | null>(null)
  const [assets, setAssets] = useState<ExpectedAsset[]>([])
  const [totalAssets, setTotalAssets] = useState(0)
  const [statistics, setStatistics] = useState<SessionStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Pagination
  const [page, setPage] = useState(1)
  const [limit] = useState(20)

  // Filters
  const [verifiedFilter, setVerifiedFilter] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')

  // Manual reading
  const [showReadingModal, setShowReadingModal] = useState(false)
  const [readingForm, setReadingForm] = useState({
    identifier: '',
    read_method: 'MANUAL',
    physical_condition: '',
    observations: ''
  })
  const [submittingReading, setSubmittingReading] = useState(false)

  // Asset detail modal
  const [selectedAsset, setSelectedAsset] = useState<ExpectedAsset | null>(null)

  // Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // Sync state
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ success: boolean; message: string; statistics?: any } | null>(null)

  // Upload state
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string; transmission_number?: string; inventory_id?: string; items_sent?: number } | null>(null)

  // Offline support
  const { isOnline, pendingCount } = useOnlineStatus()
  useServiceWorker() // Register service worker

  const loadSession = useCallback(async () => {
    try {
      const data = await inventorySessionsApi.get(sessionId)
      setSession(data)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar sessão')
    }
  }, [sessionId])

  const loadAssets = useCallback(async () => {
    try {
      const params: any = {
        skip: (page - 1) * limit,
        limit
      }

      if (verifiedFilter !== '') params.verified = verifiedFilter === 'true'
      if (searchTerm) params.search = searchTerm

      const data = await inventorySessionsApi.listExpectedAssets(sessionId, params)
      setAssets(data.items)
      setTotalAssets(data.total)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar bens')
    }
  }, [sessionId, page, limit, verifiedFilter, searchTerm])

  const loadStatistics = useCallback(async () => {
    try {
      const data = await inventorySessionsApi.getStatistics(sessionId)
      setStatistics(data)
    } catch (err) {
      console.error('Erro ao carregar estatísticas:', err)
    }
  }, [sessionId])

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true)
      await Promise.all([loadSession(), loadStatistics()])
      setLoading(false)
    }
    loadAll()
  }, [loadSession, loadStatistics])

  useEffect(() => {
    if (session) {
      loadAssets()
    }
  }, [session, loadAssets])

  // Auto-refresh statistics every 5 seconds when session is in progress
  useEffect(() => {
    if (!autoRefresh || !session || session.status !== 'in_progress') {
      return
    }

    const refreshInterval = setInterval(async () => {
      try {
        await loadStatistics()
        setLastUpdate(new Date())
      } catch (err) {
        console.error('Erro ao atualizar estatísticas:', err)
      }
    }, 5000) // 5 segundos

    return () => clearInterval(refreshInterval)
  }, [autoRefresh, session?.status, loadStatistics])

  const handleStartSession = async () => {
    try {
      await inventorySessionsApi.start(sessionId)
      loadSession()
    } catch (err: any) {
      setError(err.message || 'Erro ao iniciar sessão')
    }
  }

  const handlePauseSession = async () => {
    try {
      await inventorySessionsApi.pause(sessionId)
      loadSession()
    } catch (err: any) {
      setError(err.message || 'Erro ao pausar sessão')
    }
  }

  const handleCompleteSession = async () => {
    if (!confirm('Tem certeza que deseja finalizar esta sessão? Esta ação não pode ser desfeita.')) {
      return
    }

    try {
      await inventorySessionsApi.complete(sessionId)
      loadSession()
      loadStatistics()
    } catch (err: any) {
      setError(err.message || 'Erro ao finalizar sessão')
    }
  }

  const handleSyncAssets = async () => {
    if (!confirm('Deseja sincronizar os bens esperados do sistema externo?\n\nIsso irá baixar a lista de bens do servidor ASI.')) {
      return
    }

    setSyncing(true)
    setError(null)
    setSyncResult(null)

    try {
      const result = await inventorySessionsApi.syncExpectedAssets(sessionId, { limit: 5000 })
      setSyncResult({
        success: result.success,
        message: result.message,
        statistics: result.statistics
      })
      // Recarregar dados
      loadAssets()
      loadStatistics()
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Erro ao sincronizar bens')
      setSyncResult({
        success: false,
        message: err.response?.data?.detail || 'Falha na sincronização'
      })
    } finally {
      setSyncing(false)
    }
  }

  const handleUploadResults = async () => {
    if (!confirm('Deseja enviar os resultados do inventário para o sistema externo?\n\nIsso enviará todos os bens encontrados e não cadastrados para o servidor ASI.')) {
      return
    }

    setUploading(true)
    setError(null)
    setUploadResult(null)

    try {
      const result = await inventorySessionsApi.uploadResults(sessionId, { include_photos: false })
      setUploadResult({
        success: result.success,
        message: result.message,
        transmission_number: result.transmission_number,
        inventory_id: result.inventory_id,
        items_sent: result.items_sent
      })
      // Recarregar sessão para atualizar status
      loadSession()
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Erro ao enviar resultados')
      setUploadResult({
        success: false,
        message: err.response?.data?.detail || 'Falha no envio'
      })
    } finally {
      setUploading(false)
    }
  }

  const handleSubmitReading = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!readingForm.identifier) {
      setError('Informe um identificador (código do bem, tag RFID ou código de barras)')
      return
    }

    setSubmittingReading(true)
    setError(null)

    try {
      await inventorySessionsApi.registerReading(sessionId, {
        identifier: readingForm.identifier,
        read_method: readingForm.read_method || undefined,
        physical_condition: readingForm.physical_condition || undefined,
        observations: readingForm.observations || undefined
      })

      setShowReadingModal(false)
      setReadingForm({ identifier: '', read_method: 'MANUAL', physical_condition: '', observations: '' })
      loadAssets()
      loadStatistics()
    } catch (err: any) {
      setError(err.message || 'Erro ao registrar leitura')
    } finally {
      setSubmittingReading(false)
    }
  }

  const getAssetStatusInfo = (asset: ExpectedAsset) => {
    if (asset.reading) {
      if (asset.reading.category === 'found') {
        return { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', label: 'Encontrado' }
      }
      if (asset.reading.category === 'unregistered') {
        return { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400', label: 'Não cadastrado' }
      }
    }
    if (asset.is_written_off) {
      return { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', label: 'Baixado' }
    }
    if (asset.verified) {
      return { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', label: 'Verificado' }
    }
    return { bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-700 dark:text-gray-300', label: 'Pendente' }
  }

  const getSessionStatusBadge = (status: string) => {
    const badges: Record<string, { bg: string; text: string; label: string }> = {
      draft: { bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-700 dark:text-gray-300', label: 'Rascunho' },
      in_progress: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400', label: 'Em Andamento' },
      paused: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-700 dark:text-yellow-400', label: 'Pausada' },
      completed: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', label: 'Concluída' },
      cancelled: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', label: 'Cancelada' }
    }
    const badge = badges[status] || badges.draft
    return (
      <span className={`px-3 py-1 text-sm rounded-full ${badge.bg} ${badge.text}`}>
        {badge.label}
      </span>
    )
  }

  const totalPages = Math.ceil(totalAssets / limit)

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 dark:text-gray-400">Sessão não encontrada</p>
        <Link href="/inventario/sessoes" className="text-primary-600 hover:underline mt-2 inline-block">
          Voltar para lista
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-2">
            <Link href="/inventario/sessoes" className="hover:text-primary-600">
              Sessões
            </Link>
            <span>/</span>
            <span>{session.code}</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{session.name || session.code}</h1>
            {getSessionStatusBadge(session.status)}
          </div>
          {session.description && (
            <p className="text-gray-600 dark:text-gray-400 mt-1">{session.description}</p>
          )}
        </div>

        {/* Session Actions */}
        <div className="flex items-center gap-2">
          {/* Sync button - available for draft, in_progress, paused */}
          {(session.status === 'draft' || session.status === 'in_progress' || session.status === 'paused') && (
            <button
              onClick={handleSyncAssets}
              disabled={syncing}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {syncing ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Sincronizando...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Sincronizar Bens
                </>
              )}
            </button>
          )}

          {session.status === 'draft' && (
            <button
              onClick={handleStartSession}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              Iniciar Sessão
            </button>
          )}
          {session.status === 'in_progress' && (
            <>
              <button
                onClick={handlePauseSession}
                className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
              >
                Pausar
              </button>
              <button
                onClick={handleCompleteSession}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Finalizar
              </button>
            </>
          )}
          {session.status === 'paused' && (
            <>
              <button
                onClick={handleStartSession}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Retomar
              </button>
              <button
                onClick={handleCompleteSession}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Finalizar
              </button>
            </>
          )}

          {/* Export buttons - always visible */}
          <div className="flex items-center gap-2 ml-4 border-l border-gray-300 dark:border-gray-600 pl-4">
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/inventory/reports/${sessionId}/pdf?include_details=true`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              PDF
            </a>
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/inventory/reports/${sessionId}/excel`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 bg-green-700 text-white text-sm rounded-lg hover:bg-green-800 transition-colors flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Excel
            </a>

            {/* Upload button - only for completed sessions */}
            {session.status === 'completed' && (
              <button
                onClick={handleUploadResults}
                disabled={uploading}
                className="px-3 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-1 disabled:opacity-50"
              >
                {uploading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Enviando...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    Enviar para ASI
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Connection Status */}
      {(session.status === 'in_progress' || session.status === 'paused') && (
        <ConnectionStatusIndicator showDetails className="mb-4" />
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Fechar</button>
        </div>
      )}

      {/* Sync Result */}
      {syncResult && (
        <div className={`p-4 rounded-lg border ${
          syncResult.success
            ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
            : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        }`}>
          <div className="flex items-start justify-between">
            <div>
              <p className={`font-medium ${syncResult.success ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                {syncResult.success ? 'Sincronização concluída' : 'Falha na sincronização'}
              </p>
              <p className={`text-sm mt-1 ${syncResult.success ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}`}>
                {syncResult.message}
              </p>
              {syncResult.statistics && (
                <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  <span className="mr-4">Inseridos: {syncResult.statistics.inserted || 0}</span>
                  <span className="mr-4">Atualizados: {syncResult.statistics.updated || 0}</span>
                  <span>Erros: {syncResult.statistics.errors || 0}</span>
                </div>
              )}
            </div>
            <button
              onClick={() => setSyncResult(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Upload Result */}
      {uploadResult && (
        <div className={`p-4 rounded-lg border ${
          uploadResult.success
            ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800'
            : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        }`}>
          <div className="flex items-start justify-between">
            <div>
              <p className={`font-medium ${uploadResult.success ? 'text-purple-700 dark:text-purple-400' : 'text-red-700 dark:text-red-400'}`}>
                {uploadResult.success ? 'Envio concluído' : 'Falha no envio'}
              </p>
              <p className={`text-sm mt-1 ${uploadResult.success ? 'text-purple-600 dark:text-purple-500' : 'text-red-600 dark:text-red-500'}`}>
                {uploadResult.message}
              </p>
              {uploadResult.success && (
                <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  <span className="mr-4">Transmissão: {uploadResult.transmission_number}</span>
                  <span className="mr-4">ID Levantamento: {uploadResult.inventory_id}</span>
                  <span>Bens enviados: {uploadResult.items_sent}</span>
                </div>
              )}
            </div>
            <button
              onClick={() => setUploadResult(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Auto-refresh indicator */}
      {session.status === 'in_progress' && (
        <div className="flex items-center justify-between bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            <span className="text-sm text-blue-700 dark:text-blue-400">
              {autoRefresh ? 'Atualizando automaticamente a cada 5s' : 'Atualização automática desativada'}
            </span>
            {lastUpdate && autoRefresh && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                (última: {lastUpdate.toLocaleTimeString('pt-BR')})
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { loadStatistics(); loadAssets(); setLastUpdate(new Date()) }}
              className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Atualizar
            </button>
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded text-primary-600"
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">Auto</span>
            </label>
          </div>
        </div>
      )}

      {/* Statistics Cards */}
      {statistics && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Total Esperado</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{statistics.total_expected}</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Encontrados</p>
            <p className="text-2xl font-bold text-green-600">{statistics.total_found}</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Não Encontrados</p>
            <p className="text-2xl font-bold text-red-600">{statistics.total_not_found}</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Não Cadastrados</p>
            <p className="text-2xl font-bold text-blue-600">{statistics.total_unregistered}</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">Baixados</p>
            <p className="text-2xl font-bold text-yellow-600">{statistics.total_written_off}</p>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {statistics && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium text-gray-900 dark:text-white">Progresso do Inventário</span>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {statistics.completion_percentage.toFixed(1)}% concluído
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
            <div
              className="bg-primary-600 h-3 rounded-full transition-all duration-300"
              style={{ width: `${statistics.completion_percentage}%` }}
            />
          </div>
        </div>
      )}

      {/* Manual Reading Button */}
      {(session.status === 'in_progress' || session.status === 'paused') && (
        <div className="flex justify-end">
          <button
            onClick={() => setShowReadingModal(true)}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Registrar Leitura Manual
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Buscar
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
              placeholder="Código do bem, descrição, tag RFID..."
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
          </div>
          <div className="min-w-[150px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Status
            </label>
            <select
              value={verifiedFilter}
              onChange={(e) => { setVerifiedFilter(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="">Todos</option>
              <option value="false">Pendentes</option>
              <option value="true">Verificados</option>
            </select>
          </div>
        </div>
      </div>

      {/* Assets Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Bem
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Tags
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Localização
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Última Leitura
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {assets.map((asset) => {
                const statusInfo = getAssetStatusInfo(asset)
                return (
                  <tr key={asset.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{asset.asset_code}</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 truncate max-w-xs">
                          {asset.description || '-'}
                        </p>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      <div className="space-y-1">
                        {asset.rfid_code && <p><span className="font-medium">RFID:</span> {asset.rfid_code}</p>}
                        {asset.barcode && <p><span className="font-medium">Barras:</span> {asset.barcode}</p>}
                        {!asset.rfid_code && !asset.barcode && '-'}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      <div className="space-y-1">
                        {asset.expected_ul_code && <p><span className="font-medium">UL:</span> {asset.expected_ul_code}</p>}
                        {asset.expected_ua_code && <p><span className="font-medium">UA:</span> {asset.expected_ua_code}</p>}
                        {!asset.expected_ul_code && !asset.expected_ua_code && '-'}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${statusInfo.bg} ${statusInfo.text}`}>
                        {statusInfo.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      {asset.reading?.read_at
                        ? new Date(asset.reading.read_at).toLocaleString('pt-BR')
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelectedAsset(asset)}
                        className="text-primary-600 hover:text-primary-700 text-sm"
                      >
                        Detalhes
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {assets.length === 0 && (
          <div className="text-center py-8 text-gray-600 dark:text-gray-400">
            Nenhum bem encontrado com os filtros aplicados
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Mostrando {((page - 1) * limit) + 1} a {Math.min(page * limit, totalAssets)} de {totalAssets} bens
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

      {/* Manual Reading Modal */}
      {showReadingModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setShowReadingModal(false)} />

            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full p-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                Registrar Leitura Manual
              </h2>

              <form onSubmit={handleSubmitReading} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Identificador *
                  </label>
                  <input
                    type="text"
                    required
                    value={readingForm.identifier}
                    onChange={(e) => setReadingForm({ ...readingForm, identifier: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Código do bem, Tag RFID ou Código de barras"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Informe o código do bem, tag RFID ou código de barras
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Método de Leitura
                  </label>
                  <select
                    value={readingForm.read_method}
                    onChange={(e) => setReadingForm({ ...readingForm, read_method: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="MANUAL">Manual</option>
                    <option value="RFID">RFID</option>
                    <option value="BARCODE">Código de Barras</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Estado Físico
                  </label>
                  <select
                    value={readingForm.physical_condition}
                    onChange={(e) => setReadingForm({ ...readingForm, physical_condition: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="">Não informado</option>
                    <option value="BOM">Bom</option>
                    <option value="REGULAR">Regular</option>
                    <option value="RUIM">Ruim</option>
                    <option value="INSERVIVEL">Inservível</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Observações
                  </label>
                  <textarea
                    value={readingForm.observations}
                    onChange={(e) => setReadingForm({ ...readingForm, observations: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Notas adicionais..."
                  />
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowReadingModal(false)}
                    className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={submittingReading || !readingForm.identifier}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                  >
                    {submittingReading ? 'Registrando...' : 'Registrar'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Asset Detail Modal */}
      {selectedAsset && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setSelectedAsset(null)} />

            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full p-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                Detalhes do Bem
              </h2>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Código do Bem</p>
                    <p className="font-medium text-gray-900 dark:text-white">{selectedAsset.asset_code}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
                    {(() => {
                      const statusInfo = getAssetStatusInfo(selectedAsset)
                      return (
                        <span className={`px-2 py-1 text-xs rounded-full ${statusInfo.bg} ${statusInfo.text}`}>
                          {statusInfo.label}
                        </span>
                      )
                    })()}
                  </div>
                </div>

                {selectedAsset.description && (
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Descrição</p>
                    <p className="text-gray-900 dark:text-white">{selectedAsset.description}</p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Tag RFID</p>
                    <p className="text-gray-900 dark:text-white">{selectedAsset.rfid_code || '-'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Código de Barras</p>
                    <p className="text-gray-900 dark:text-white">{selectedAsset.barcode || '-'}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">UL Esperada</p>
                    <p className="text-gray-900 dark:text-white">{selectedAsset.expected_ul_code || '-'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">UA Esperada</p>
                    <p className="text-gray-900 dark:text-white">{selectedAsset.expected_ua_code || '-'}</p>
                  </div>
                </div>

                {selectedAsset.category && (
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Categoria</p>
                    <p className="text-gray-900 dark:text-white">{selectedAsset.category}</p>
                  </div>
                )}

                {selectedAsset.reading && (
                  <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                    <p className="font-medium text-gray-900 dark:text-white mb-2">Última Leitura</p>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Data</p>
                        <p className="text-gray-900 dark:text-white">
                          {new Date(selectedAsset.reading.read_at).toLocaleString('pt-BR')}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Método</p>
                        <p className="text-gray-900 dark:text-white">{selectedAsset.reading.read_method}</p>
                      </div>
                      {selectedAsset.reading.physical_condition && (
                        <div>
                          <p className="text-gray-500 dark:text-gray-400">Estado Físico</p>
                          <p className="text-gray-900 dark:text-white">{selectedAsset.reading.physical_condition}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-4">
                <button
                  onClick={() => setSelectedAsset(null)}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Fechar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
