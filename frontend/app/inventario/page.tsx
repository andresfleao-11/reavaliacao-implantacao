'use client'

import { useState, useEffect } from 'react'
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

export default function InventarioPage() {
  const { user } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<string>('')
  const [readItems, setReadItems] = useState<ReadItem[]>([])
  const [scannerOpen, setScannerOpen] = useState(false)
  const [manualCode, setManualCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null)
  const [location, setLocation] = useState('')

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

  // Adicionar item lido
  const addItem = (code: string, type: 'barcode' | 'rfid', rssi?: string) => {
    // Verificar duplicata
    if (readItems.some(item => item.code === code)) {
      setMessage({ type: 'error', text: `Código ${code} já foi lido` })
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

    // Vibrar se disponível
    if (navigator.vibrate) {
      navigator.vibrate(100)
    }
  }

  // Callback do scanner de código de barras
  const handleBarcodeScan = (code: string) => {
    addItem(code, 'barcode')
    setScannerOpen(false)
  }

  // Adicionar código manualmente
  const handleManualAdd = () => {
    if (manualCode.trim()) {
      addItem(manualCode.trim(), 'barcode')
      setManualCode('')
    }
  }

  // Remover item
  const removeItem = (id: string) => {
    setReadItems(prev => prev.filter(item => item.id !== id))
  }

  // Limpar todos
  const clearAll = () => {
    if (confirm('Deseja limpar todas as leituras?')) {
      setReadItems([])
    }
  }

  // Sincronizar com servidor (para RFID)
  const syncToServer = async () => {
    if (readItems.length === 0) {
      setMessage({ type: 'error', text: 'Nenhum item para enviar' })
      return
    }

    setSyncing(true)
    setMessage(null)

    try {
      const token = localStorage.getItem('token')
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
      setMessage({ type: 'error', text: 'Erro de conexão com o servidor' })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
          Inventário - Nova Leitura
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

      {/* Configurações */}
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
            >
              <option value="">Sem vínculo com projeto</option>
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
      </div>

      {/* Área de leitura */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Método de Leitura
        </h2>

        {/* Botões de leitura */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          {/* Scanner de código de barras - Câmera (Mobile) */}
          <button
            onClick={() => setScannerOpen(true)}
            className="flex items-center justify-center gap-3 p-4 bg-primary-50 dark:bg-primary-900/20 border-2 border-primary-200 dark:border-primary-800 rounded-lg hover:bg-primary-100 dark:hover:bg-primary-900/30 transition-colors sm:hidden"
          >
            <svg className="w-8 h-8 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12h2m2 0h.01M4 4h4M4 8h4m4 12h2M4 16h4m12-4h.01M12 20h.01" />
            </svg>
            <div className="text-left">
              <p className="font-medium text-primary-700 dark:text-primary-300">Código de Barras</p>
              <p className="text-sm text-primary-600 dark:text-primary-400">Usar câmera</p>
            </div>
          </button>

          {/* Barcode via Middleware */}
          <div className="flex items-center justify-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-200 dark:border-blue-800 rounded-lg">
            <svg className="w-8 h-8 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12h2m2 0h.01M4 4h4M4 8h4m4 12h2M4 16h4m12-4h.01M12 20h.01" />
            </svg>
            <div className="text-left">
              <p className="font-medium text-blue-700 dark:text-blue-300">Código de Barras</p>
              <p className="text-sm text-blue-600 dark:text-blue-400">Use o app Middleware</p>
            </div>
          </div>

          {/* RFID via Middleware */}
          <div className="flex items-center justify-center gap-3 p-4 bg-orange-50 dark:bg-orange-900/20 border-2 border-orange-200 dark:border-orange-800 rounded-lg">
            <svg className="w-8 h-8 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
            <div className="text-left">
              <p className="font-medium text-orange-700 dark:text-orange-300">RFID</p>
              <p className="text-sm text-orange-600 dark:text-orange-400">Use o app Middleware</p>
            </div>
          </div>
        </div>

        {/* Entrada manual */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
              Inserir código manualmente
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
                placeholder="Digite o código do item..."
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
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 sm:hidden">
            Pressione Enter para adicionar rapidamente
          </p>
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
            <p className="text-sm mt-1">Use o scanner ou digite o código manualmente</p>
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

      {/* Scanner de código de barras */}
      <BarcodeScanner
        isOpen={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={handleBarcodeScan}
      />
    </div>
  )
}
