'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { API_URL } from '@/lib/api'

interface Project {
  id: number
  nome: string
  client?: { nome: string; nome_curto?: string }
}

interface ActiveSession {
  id: number
  created_at: string
  reading_type: 'RFID' | 'BARCODE'
  status: string
  user_id: number
  project_id?: number
  location?: string
  timeout_seconds: number
  readings_count: number
}

interface SessionReading {
  id: number
  created_at: string
  code: string
  rssi?: string
  device_id?: string
}

interface PastSession {
  id: number
  created_at: string
  reading_type: 'RFID' | 'BARCODE'
  status: string
  readings_count: number
  location?: string
  project_id?: number
}

export default function InventarioPage() {
  const { user } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<string>('')
  const [location, setLocation] = useState('')
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null)

  // Estados para sessao ativa
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null)
  const [startingSession, setStartingSession] = useState<'RFID' | 'BARCODE' | null>(null)
  const [sessionReadings, setSessionReadings] = useState<SessionReading[]>([])
  const [timeRemaining, setTimeRemaining] = useState(0)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Estados para sessoes anteriores
  const [pastSessions, setPastSessions] = useState<PastSession[]>([])
  const [expandedSession, setExpandedSession] = useState<number | null>(null)
  const [expandedReadings, setExpandedReadings] = useState<SessionReading[]>([])
  const [loadingReadings, setLoadingReadings] = useState(false)

  const getToken = () => localStorage.getItem('access_token')

  // Carregar projetos
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await fetch(`${API_URL}/api/projects?per_page=100`)
        const data = await res.json()
        setProjects(data.items || [])
      } catch (err) {
        console.error('Erro ao carregar projetos:', err)
      }
    }
    fetchProjects()
  }, [])

  // Verificar sessao ativa e carregar sessoes anteriores
  useEffect(() => {
    checkActiveSession()
    fetchPastSessions()
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [])

  // Polling para leituras quando ha sessao ativa
  useEffect(() => {
    if (activeSession && activeSession.status === 'ACTIVE') {
      pollIntervalRef.current = setInterval(() => {
        fetchSessionReadings(activeSession.id)
      }, 2000)

      return () => {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }
      }
    }
  }, [activeSession])

  // Timer para atualizar tempo restante
  useEffect(() => {
    if (activeSession && activeSession.status === 'ACTIVE') {
      const timer = setInterval(() => {
        const created = new Date(activeSession.created_at)
        const expiresAt = new Date(created.getTime() + activeSession.timeout_seconds * 1000)
        const remaining = Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000))
        setTimeRemaining(remaining)

        if (remaining <= 0) {
          checkActiveSession()
          fetchPastSessions()
        }
      }, 1000)
      return () => clearInterval(timer)
    }
  }, [activeSession])

  const checkActiveSession = async () => {
    try {
      const token = getToken()
      const res = await fetch(`${API_URL}/api/reading-sessions/active`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        const data = await res.json()
        if (data) {
          setActiveSession(data)
          fetchSessionReadings(data.id)
        } else {
          setActiveSession(null)
          setSessionReadings([])
        }
      }
    } catch (err) {
      console.error('Erro ao verificar sessao:', err)
    }
  }

  const fetchSessionReadings = async (sessionId: number) => {
    try {
      const token = getToken()
      const res = await fetch(`${API_URL}/api/reading-sessions/${sessionId}/readings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        const data = await res.json()
        setSessionReadings(data)
      }
    } catch (err) {
      console.error('Erro ao buscar leituras:', err)
    }
  }

  const fetchPastSessions = async () => {
    try {
      const token = getToken()
      const res = await fetch(`${API_URL}/api/reading-sessions?limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        const data = await res.json()
        // Filtrar apenas sessoes finalizadas ou expiradas
        setPastSessions(data.filter((s: PastSession) => s.status !== 'ACTIVE'))
      }
    } catch (err) {
      console.error('Erro ao buscar sessoes:', err)
    }
  }

  const fetchExpandedReadings = async (sessionId: number) => {
    if (expandedSession === sessionId) {
      setExpandedSession(null)
      setExpandedReadings([])
      return
    }

    setLoadingReadings(true)
    setExpandedSession(sessionId)

    try {
      const token = getToken()
      const res = await fetch(`${API_URL}/api/reading-sessions/${sessionId}/readings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        const data = await res.json()
        setExpandedReadings(data)
      }
    } catch (err) {
      console.error('Erro ao buscar leituras:', err)
    } finally {
      setLoadingReadings(false)
    }
  }

  const startSession = async (readingType: 'RFID' | 'BARCODE') => {
    setStartingSession(readingType)
    setMessage(null)

    try {
      const token = getToken()
      const payload = {
        reading_type: readingType,
        project_id: selectedProject ? parseInt(selectedProject) : null,
        location: location || null,
        timeout_seconds: 300
      }

      const res = await fetch(`${API_URL}/api/reading-sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        const data = await res.json()
        setActiveSession(data)
        setSessionReadings([])
        setTimeRemaining(data.timeout_seconds)
      } else {
        const error = await res.json()
        setMessage({ type: 'error', text: error.detail || 'Erro ao iniciar sessao' })
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro de conexao com o servidor' })
    } finally {
      setStartingSession(null)
    }
  }

  const completeSession = async () => {
    if (!activeSession) return

    try {
      const token = getToken()
      const res = await fetch(`${API_URL}/api/reading-sessions/${activeSession.id}/complete`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        setMessage({
          type: 'success',
          text: `Sessao finalizada com ${sessionReadings.length} leitura(s) gravada(s)!`
        })
        setActiveSession(null)
        setSessionReadings([])
        fetchPastSessions()

        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro ao finalizar sessao' })
    }
  }

  const cancelSession = async () => {
    if (!activeSession) return

    try {
      const token = getToken()
      await fetch(`${API_URL}/api/reading-sessions/${activeSession.id}/cancel`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      setActiveSession(null)
      setSessionReadings([])
      fetchPastSessions()
      setMessage({ type: 'success', text: 'Sessao cancelada' })

      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro ao cancelar sessao' })
    }
  }

  const openMiddlewareApp = () => {
    if (!activeSession) return
    const deepLink = `rfidmiddleware://reading?type=${activeSession.reading_type}&session_id=${activeSession.id}`
    window.location.href = deepLink
  }

  const formatTimeRemaining = () => {
    const minutes = Math.floor(timeRemaining / 60)
    const secs = timeRemaining % 60
    return `${minutes}:${secs.toString().padStart(2, '0')}`
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

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      'COMPLETED': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
      'CANCELLED': 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
      'EXPIRED': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
      'ACTIVE': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
    }
    const labels: Record<string, string> = {
      'COMPLETED': 'Finalizada',
      'CANCELLED': 'Cancelada',
      'EXPIRED': 'Expirada',
      'ACTIVE': 'Ativa'
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${styles[status] || styles['CANCELLED']}`}>
        {labels[status] || status}
      </span>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
          Inventario - Leitura RFID/Barcode
        </h1>
      </div>

      {/* Mensagem de feedback */}
      {message && (
        <div className={`mb-4 p-3 rounded-lg ${
          message.type === 'success'
            ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800'
            : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
        }`}>
          {message.text}
        </div>
      )}

      {/* Configuracoes - apenas se nao tiver sessao ativa */}
      {!activeSession && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Nova Sessao de Leitura
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Projeto (opcional)
              </label>
              <select
                value={selectedProject}
                onChange={(e) => setSelectedProject(e.target.value)}
                className="input-field w-full"
              >
                <option value="">Sem vinculo com projeto</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome} {p.client ? `(${p.client.nome_curto || p.client.nome})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Local (opcional)
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className="input-field w-full"
                placeholder="Ex: Sala 101, Almoxarifado"
              />
            </div>
          </div>

          {/* Botoes de sessao */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={() => startSession('RFID')}
              disabled={startingSession !== null}
              className="flex items-center justify-center gap-3 p-6 border-2 rounded-xl transition-all bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-900/30 border-orange-200 dark:border-orange-800 hover:border-orange-400 hover:shadow-lg"
            >
              {startingSession === 'RFID' ? (
                <svg className="animate-spin w-10 h-10 text-orange-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-10 h-10 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
              )}
              <div className="text-left">
                <p className="text-lg font-semibold text-orange-700 dark:text-orange-300">Leitura RFID</p>
                <p className="text-sm text-orange-600 dark:text-orange-400">Tags e etiquetas</p>
              </div>
            </button>

            <button
              onClick={() => startSession('BARCODE')}
              disabled={startingSession !== null}
              className="flex items-center justify-center gap-3 p-6 border-2 rounded-xl transition-all bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-900/30 border-blue-200 dark:border-blue-800 hover:border-blue-400 hover:shadow-lg"
            >
              {startingSession === 'BARCODE' ? (
                <svg className="animate-spin w-10 h-10 text-blue-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-10 h-10 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12h2m2 0h.01M4 4h4M4 8h4m4 12h2M4 16h4m12-4h.01M12 20h.01" />
                </svg>
              )}
              <div className="text-left">
                <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">Leitura Barcode</p>
                <p className="text-sm text-blue-600 dark:text-blue-400">Codigos de barras</p>
              </div>
            </button>
          </div>
        </div>
      )}

      {/* Sessao Ativa */}
      {activeSession && (
        <div className="card mb-6 border-2 border-green-300 dark:border-green-700">
          <div className={`-mx-6 -mt-6 px-6 py-4 mb-4 ${
            activeSession.reading_type === 'RFID'
              ? 'bg-gradient-to-r from-orange-500 to-orange-600'
              : 'bg-gradient-to-r from-blue-500 to-blue-600'
          }`}>
            <div className="flex items-center justify-between text-white">
              <div className="flex items-center gap-3">
                <div className="animate-pulse">
                  <div className="w-3 h-3 bg-white rounded-full"></div>
                </div>
                <div>
                  <h2 className="text-lg font-bold">Sessao {activeSession.reading_type} Ativa</h2>
                  <p className="text-sm opacity-90">Aguardando leituras do app...</p>
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-mono font-bold">{formatTimeRemaining()}</div>
                <div className="text-xs opacity-75">restantes</div>
              </div>
            </div>
          </div>

          {/* Botao para abrir app */}
          <button
            onClick={openMiddlewareApp}
            className={`w-full py-4 rounded-xl text-white font-semibold flex items-center justify-center gap-3 mb-4 ${
              activeSession.reading_type === 'RFID'
                ? 'bg-orange-500 hover:bg-orange-600'
                : 'bg-blue-500 hover:bg-blue-600'
            } transition-colors`}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            Abrir App Middleware
          </button>

          {/* Contador e leituras */}
          <div className="text-center mb-4">
            <div className="text-4xl font-bold text-gray-900 dark:text-gray-100">
              {sessionReadings.length}
            </div>
            <div className="text-gray-500 dark:text-gray-400">
              leitura{sessionReadings.length !== 1 ? 's' : ''} recebida{sessionReadings.length !== 1 ? 's' : ''}
            </div>
          </div>

          {/* Lista de leituras */}
          {sessionReadings.length > 0 && (
            <div className="mb-4 max-h-48 overflow-y-auto border rounded-lg dark:border-gray-700">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-gray-700 dark:text-gray-300">Codigo</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-700 dark:text-gray-300">RSSI</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-700 dark:text-gray-300">Hora</th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-gray-700">
                  {sessionReadings.map((reading) => (
                    <tr key={reading.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-3 py-2 font-mono text-gray-900 dark:text-gray-100">{reading.code}</td>
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-400">{reading.rssi || '-'}</td>
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-400">
                        {new Date(reading.created_at).toLocaleTimeString('pt-BR')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Botoes de acao */}
          <div className="flex gap-3">
            <button
              onClick={cancelSession}
              className="flex-1 py-3 rounded-xl border-2 border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={completeSession}
              className="flex-1 py-3 rounded-xl bg-green-500 hover:bg-green-600 text-white font-medium transition-colors"
            >
              Finalizar ({sessionReadings.length})
            </button>
          </div>
        </div>
      )}

      {/* Historico de Sessoes */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Historico de Leituras
        </h2>

        {pastSessions.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <p>Nenhuma sessao de leitura realizada</p>
          </div>
        ) : (
          <div className="space-y-3">
            {pastSessions.map((session) => (
              <div key={session.id} className="border rounded-lg dark:border-gray-700 overflow-hidden">
                <button
                  onClick={() => fetchExpandedReadings(session.id)}
                  className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      session.reading_type === 'RFID'
                        ? 'bg-orange-100 dark:bg-orange-900/30'
                        : 'bg-blue-100 dark:bg-blue-900/30'
                    }`}>
                      {session.reading_type === 'RFID' ? (
                        <svg className="w-5 h-5 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12h2m2 0h.01M4 4h4M4 8h4m4 12h2M4 16h4m12-4h.01M12 20h.01" />
                        </svg>
                      )}
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-gray-100">
                          Sessao #{session.id}
                        </span>
                        {getStatusBadge(session.status)}
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        {formatDate(session.created_at)}
                        {session.location && ` • ${session.location}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {session.readings_count}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">leituras</div>
                    </div>
                    <svg
                      className={`w-5 h-5 text-gray-400 transition-transform ${expandedSession === session.id ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Leituras expandidas */}
                {expandedSession === session.id && (
                  <div className="border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    {loadingReadings ? (
                      <div className="p-4 text-center text-gray-500">Carregando...</div>
                    ) : expandedReadings.length === 0 ? (
                      <div className="p-4 text-center text-gray-500">Nenhuma leitura nesta sessao</div>
                    ) : (
                      <div className="max-h-64 overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-100 dark:bg-gray-800 sticky top-0">
                            <tr>
                              <th className="text-left px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Codigo</th>
                              <th className="text-left px-4 py-2 font-medium text-gray-700 dark:text-gray-300">RSSI</th>
                              <th className="text-left px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Hora</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y dark:divide-gray-700">
                            {expandedReadings.map((reading) => (
                              <tr key={reading.id}>
                                <td className="px-4 py-2 font-mono text-gray-900 dark:text-gray-100">{reading.code}</td>
                                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{reading.rssi || '-'}</td>
                                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                                  {new Date(reading.created_at).toLocaleTimeString('pt-BR')}
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
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
