'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { API_URL } from '@/lib/api'
import BarcodeScanner from '@/components/BarcodeScanner'

interface Project {
  id: number
  nome: string
  client?: { nome: string; nome_curto?: string }
}

interface ReadItem {
  id: string
  code: string
  type: 'barcode' | 'rfid'
  timestamp: Date
  rssi?: string
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

export default function InventarioPage() {
  const { user } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<string>('')
  const [readItems, setReadItems] = useState<ReadItem[]>([])
  const [scannerOpen, setScannerOpen] = useState(false)
  const [manualCode, setManualCode] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null)
  const [location, setLocation] = useState('')

  // Estados para sessao
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null)
  const [startingSession, setStartingSession] = useState<'RFID' | 'BARCODE' | null>(null)
  const [sessionReadings, setSessionReadings] = useState<SessionReading[]>([])
  const [showWaitingModal, setShowWaitingModal] = useState(false)
  const [timeRemaining, setTimeRemaining] = useState(0)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

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

  // Verificar sessao ativa ao carregar
  useEffect(() => {
    checkActiveSession()
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
    if (activeSession && showWaitingModal) {
      const timer = setInterval(() => {
        const created = new Date(activeSession.created_at)
        const expiresAt = new Date(created.getTime() + activeSession.timeout_seconds * 1000)
        const remaining = Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000))
        setTimeRemaining(remaining)

        if (remaining <= 0) {
          setActiveSession(null)
          setShowWaitingModal(false)
          setMessage({ type: 'error', text: 'Sessao expirada' })
        }
      }, 1000)
      return () => clearInterval(timer)
    }
  }, [activeSession, showWaitingModal])

  const getToken = () => localStorage.getItem('access_token')

  const checkActiveSession = async () => {
    try {
      const token = getToken()
      const res = await fetch(`${API_URL}/api/reading-sessions/active`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (res.ok) {
        const data = await res.json()
        if (data) {
          setActiveSession(data)
          setShowWaitingModal(true)
          fetchSessionReadings(data.id)
        } else {
          setActiveSession(null)
          setShowWaitingModal(false)
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
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (res.ok) {
        const data = await res.json()
        setSessionReadings(data)
      }
    } catch (err) {
      console.error('Erro ao buscar leituras:', err)
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
        setShowWaitingModal(true)
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
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (res.ok) {
        const newItems: ReadItem[] = sessionReadings.map(reading => ({
          id: `session-${reading.id}`,
          code: reading.code,
          type: activeSession.reading_type === 'RFID' ? 'rfid' : 'barcode',
          timestamp: new Date(reading.created_at),
          rssi: reading.rssi
        }))

        setReadItems(prev => {
          const existingCodes = new Set(prev.map(i => i.code))
          const uniqueNew = newItems.filter(i => !existingCodes.has(i.code))
          return [...uniqueNew, ...prev]
        })

        setActiveSession(null)
        setSessionReadings([])
        setShowWaitingModal(false)
        setMessage({ type: 'success', text: `Sessao finalizada! ${sessionReadings.length} leituras recebidas.` })

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
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      setActiveSession(null)
      setSessionReadings([])
      setShowWaitingModal(false)
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

  // Adicionar item lido (manual)
  const addItem = (code: string, type: 'barcode' | 'rfid', rssi?: string) => {
    if (readItems.some(item => item.code === code)) {
      setMessage({ type: 'error', text: `Codigo ${code} ja foi lido` })
      setTimeout(() => setMessage(null), 3000)
      return
    }

    const newItem: ReadItem = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      code,
      type,
      timestamp: new Date(),
      rssi
    }
    setReadItems(prev => [newItem, ...prev])

    if (navigator.vibrate) {
      navigator.vibrate(100)
    }
  }

  const handleBarcodeScan = (code: string) => {
    addItem(code, 'barcode')
    setScannerOpen(false)
  }

  const handleManualAdd = () => {
    if (manualCode.trim()) {
      addItem(manualCode.trim(), 'barcode')
      setManualCode('')
    }
  }

  const removeItem = (id: string) => {
    setReadItems(prev => prev.filter(item => item.id !== id))
  }

  const clearAll = () => {
    if (confirm('Deseja limpar todas as leituras?')) {
      setReadItems([])
    }
  }

  const syncToServer = async () => {
    if (readItems.length === 0) {
      setMessage({ type: 'error', text: 'Nenhum item para enviar' })
      return
    }

    setSyncing(true)
    setMessage(null)

    try {
      const token = getToken()
      const batchId = `WEB-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

      const payload = {
        device_id: 'WEB-Browser',
        batch_id: batchId,
        location: location || null,
        project_id: selectedProject ? parseInt(selectedProject) : null,
        tags: readItems.map(item => ({
          epc: item.code,
          rssi: item.rssi || '0',
          timestamp: item.timestamp.toISOString()
        }))
      }

      const response = await fetch(`${API_URL}/api/rfid/tags`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      })

      if (response.ok) {
        const data = await response.json()
        setMessage({ type: 'success', text: `${data.received_count} itens enviados com sucesso!` })
        setReadItems([])
      } else {
        const error = await response.json()
        setMessage({ type: 'error', text: error.detail || 'Erro ao enviar dados' })
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro de conexao com o servidor' })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Modal de Espera */}
      {showWaitingModal && activeSession && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
            {/* Header com gradiente */}
            <div className={`p-6 text-white ${
              activeSession.reading_type === 'RFID'
                ? 'bg-gradient-to-r from-orange-500 to-orange-600'
                : 'bg-gradient-to-r from-blue-500 to-blue-600'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="animate-pulse">
                    <div className="w-4 h-4 bg-white rounded-full"></div>
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Sessao {activeSession.reading_type}</h2>
                    <p className="text-sm opacity-90">Aguardando leituras do app</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-mono font-bold">{formatTimeRemaining()}</div>
                  <div className="text-xs opacity-75">restantes</div>
                </div>
              </div>
            </div>

            {/* Conteudo */}
            <div className="p-6">
              {/* Contador de leituras */}
              <div className="text-center mb-6">
                <div className="text-5xl font-bold text-gray-900 dark:text-gray-100">
                  {sessionReadings.length}
                </div>
                <div className="text-gray-500 dark:text-gray-400">
                  leitura{sessionReadings.length !== 1 ? 's' : ''} recebida{sessionReadings.length !== 1 ? 's' : ''}
                </div>
              </div>

              {/* Lista de leituras recentes */}
              {sessionReadings.length > 0 && (
                <div className="mb-6 max-h-32 overflow-y-auto">
                  <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Ultimas leituras:</div>
                  <div className="space-y-1">
                    {sessionReadings.slice(0, 5).map((reading) => (
                      <div
                        key={reading.id}
                        className="bg-gray-100 dark:bg-gray-700 px-3 py-2 rounded text-sm font-mono truncate"
                      >
                        {reading.code}
                      </div>
                    ))}
                    {sessionReadings.length > 5 && (
                      <div className="text-xs text-gray-400 text-center">
                        +{sessionReadings.length - 5} mais...
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Botao para abrir o app */}
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

              <p className="text-xs text-gray-500 dark:text-gray-400 text-center mb-6">
                Clique acima para abrir o app diretamente na tela de leitura {activeSession.reading_type}
              </p>

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
                  disabled={sessionReadings.length === 0}
                  className={`flex-1 py-3 rounded-xl font-medium transition-colors ${
                    sessionReadings.length > 0
                      ? 'bg-green-500 hover:bg-green-600 text-white'
                      : 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  Finalizar ({sessionReadings.length})
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
          Inventario - Nova Leitura
        </h1>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {readItems.length} item(s) lido(s)
        </span>
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

      {/* Configuracoes */}
      <div className="card mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Projeto (opcional)
            </label>
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="input-field w-full"
              disabled={!!activeSession}
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
              disabled={!!activeSession}
            />
          </div>
        </div>
      </div>

      {/* Area de leitura */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Iniciar Leitura via App Middleware
        </h2>

        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Clique em um dos botoes abaixo para iniciar uma sessao de leitura. O app sera aberto automaticamente no modo correto.
        </p>

        {/* Botoes de sessao */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          {/* Botao RFID */}
          <button
            onClick={() => startSession('RFID')}
            disabled={!!activeSession || startingSession !== null}
            className={`flex items-center justify-center gap-3 p-6 border-2 rounded-xl transition-all ${
              activeSession
                ? 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 opacity-50 cursor-not-allowed'
                : 'bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-900/30 border-orange-200 dark:border-orange-800 hover:border-orange-400 hover:shadow-lg cursor-pointer'
            }`}
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
              <p className="text-lg font-semibold text-orange-700 dark:text-orange-300">
                Leitura RFID
              </p>
              <p className="text-sm text-orange-600 dark:text-orange-400">
                Tags e etiquetas
              </p>
            </div>
          </button>

          {/* Botao Barcode */}
          <button
            onClick={() => startSession('BARCODE')}
            disabled={!!activeSession || startingSession !== null}
            className={`flex items-center justify-center gap-3 p-6 border-2 rounded-xl transition-all ${
              activeSession
                ? 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 opacity-50 cursor-not-allowed'
                : 'bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-900/30 border-blue-200 dark:border-blue-800 hover:border-blue-400 hover:shadow-lg cursor-pointer'
            }`}
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
              <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">
                Leitura Barcode
              </p>
              <p className="text-sm text-blue-600 dark:text-blue-400">
                Codigos de barras
              </p>
            </div>
          </button>
        </div>

        {/* Scanner de codigo de barras - Camera (Mobile) */}
        <button
          onClick={() => setScannerOpen(true)}
          className="w-full flex items-center justify-center gap-3 p-4 bg-purple-50 dark:bg-purple-900/20 border-2 border-purple-200 dark:border-purple-800 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors sm:hidden mb-4"
        >
          <svg className="w-8 h-8 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <div className="text-left">
            <p className="font-medium text-purple-700 dark:text-purple-300">Usar Camera</p>
            <p className="text-sm text-purple-600 dark:text-purple-400">Escanear codigo de barras</p>
          </div>
        </button>

        {/* Entrada manual */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
              Inserir codigo manualmente
            </span>
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleManualAdd()}
                className="input-field w-full text-base py-3 sm:py-2 pr-10"
                placeholder="Digite o codigo do item..."
              />
              {manualCode && (
                <button
                  type="button"
                  onClick={() => setManualCode('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <button
              onClick={handleManualAdd}
              disabled={!manualCode.trim()}
              className="btn-primary px-6 py-3 sm:py-2 w-full sm:w-auto text-base sm:text-sm font-medium"
            >
              <span className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Adicionar
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Lista de itens lidos */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Itens Lidos ({readItems.length})
          </h2>
          <div className="flex gap-2">
            {readItems.length > 0 && (
              <>
                <button
                  onClick={clearAll}
                  className="btn-secondary text-sm px-3 py-1"
                >
                  Limpar
                </button>
                <button
                  onClick={syncToServer}
                  disabled={syncing}
                  className="btn-primary text-sm px-3 py-1 flex items-center gap-2"
                >
                  {syncing ? (
                    <>
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Enviando...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      Enviar
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>

        {readItems.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <p>Nenhum item lido ainda</p>
            <p className="text-sm mt-1">Inicie uma sessao de leitura ou digite o codigo manualmente</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {readItems.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 text-xs font-medium rounded ${
                    item.type === 'rfid'
                      ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300'
                      : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                  }`}>
                    {item.type === 'rfid' ? 'RFID' : 'Barcode'}
                  </span>
                  <div>
                    <p className="font-mono text-sm text-gray-900 dark:text-gray-100">
                      {item.code}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {item.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeItem(item.id)}
                  className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Scanner de codigo de barras */}
      <BarcodeScanner
        isOpen={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={handleBarcodeScan}
      />
    </div>
  )
}
