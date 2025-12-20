'use client'

import { useState, useEffect } from 'react'
import { externalSystemsApi, ExternalSystem, ExternalSystemCreate, ConnectionTestResult, SyncResult } from '@/lib/api'

type SystemType = 'asi' | 'sap' | 'totvs' | 'custom'
type AuthType = 'none' | 'basic' | 'token' | 'header'

export default function SistemasExternosPage() {
  const [systems, setSystems] = useState<ExternalSystem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal states
  const [showModal, setShowModal] = useState(false)
  const [editingSystem, setEditingSystem] = useState<ExternalSystem | null>(null)
  const [formData, setFormData] = useState<ExternalSystemCreate>({
    name: '',
    system_type: 'asi',
    host: '',
    port: undefined,
    context_path: '',
    full_url: '',
    auth_type: 'basic',
    auth_username: '',
    auth_password: '',
    auth_token: '',
    auth_header_name: '',
    timeout_seconds: 30,
    retry_attempts: 3,
    double_json_encoding: false,
    is_default: false
  })
  const [saving, setSaving] = useState(false)

  // Test/Sync states
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ id: number; result: ConnectionTestResult } | null>(null)
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [syncResult, setSyncResult] = useState<{ id: number; result: Record<string, SyncResult> } | null>(null)

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<number | null>(null)

  useEffect(() => {
    loadSystems()
  }, [])

  const loadSystems = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await externalSystemsApi.list()
      setSystems(data)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar sistemas')
    } finally {
      setLoading(false)
    }
  }

  const openCreateModal = () => {
    setEditingSystem(null)
    setFormData({
      name: '',
      system_type: 'asi',
      host: '',
      port: undefined,
      context_path: '',
      full_url: '',
      auth_type: 'basic',
      auth_username: '',
      auth_password: '',
      auth_token: '',
      auth_header_name: '',
      timeout_seconds: 30,
      retry_attempts: 3,
      double_json_encoding: false,
      is_default: false
    })
    setShowModal(true)
  }

  const openEditModal = (system: ExternalSystem) => {
    setEditingSystem(system)
    setFormData({
      name: system.name,
      system_type: system.system_type,
      host: system.host,
      port: system.port || undefined,
      context_path: system.context_path || '',
      full_url: system.full_url || '',
      auth_type: system.auth_type,
      auth_username: system.auth_username || '',
      auth_password: '', // Don't show existing password
      auth_token: '',
      auth_header_name: '',
      timeout_seconds: system.timeout_seconds,
      retry_attempts: system.retry_attempts,
      double_json_encoding: system.double_json_encoding,
      is_default: system.is_default
    })
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    try {
      const dataToSend: ExternalSystemCreate = {
        name: formData.name,
        system_type: formData.system_type,
        host: formData.host,
        auth_type: formData.auth_type,
        port: formData.port || undefined,
        context_path: formData.context_path || undefined,
        full_url: formData.full_url || undefined,
        timeout_seconds: formData.timeout_seconds,
        retry_attempts: formData.retry_attempts,
        double_json_encoding: formData.double_json_encoding,
        is_default: formData.is_default
      }

      // Add auth fields based on auth type
      if (formData.auth_type === 'basic') {
        dataToSend.auth_username = formData.auth_username || undefined
        if (formData.auth_password) {
          dataToSend.auth_password = formData.auth_password
        }
      } else if (formData.auth_type === 'token') {
        if (formData.auth_token) {
          dataToSend.auth_token = formData.auth_token
        }
      } else if (formData.auth_type === 'header') {
        dataToSend.auth_header_name = formData.auth_header_name || undefined
        if (formData.auth_token) {
          dataToSend.auth_token = formData.auth_token
        }
      }

      if (editingSystem) {
        await externalSystemsApi.update(editingSystem.id, dataToSend)
      } else {
        await externalSystemsApi.create(dataToSend)
      }

      setShowModal(false)
      loadSystems()
    } catch (err: any) {
      setError(err.message || 'Erro ao salvar sistema')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await externalSystemsApi.delete(id)
      setDeletingId(null)
      loadSystems()
    } catch (err: any) {
      setError(err.message || 'Erro ao excluir sistema')
    }
  }

  const handleTestConnection = async (id: number) => {
    setTestingId(id)
    setTestResult(null)

    try {
      const result = await externalSystemsApi.testConnection(id)
      setTestResult({ id, result })
    } catch (err: any) {
      setTestResult({
        id,
        result: {
          success: false,
          message: err.message || 'Erro ao testar conexão',
          response_time_ms: 0
        }
      })
    } finally {
      setTestingId(null)
    }
  }

  const handleSync = async (id: number) => {
    setSyncingId(id)
    setSyncResult(null)

    try {
      const result = await externalSystemsApi.sync(id)
      setSyncResult({ id, result })
    } catch (err: any) {
      setError(err.message || 'Erro ao sincronizar')
    } finally {
      setSyncingId(null)
    }
  }

  const getSystemTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      asi: 'ASI Patrimônio',
      sap: 'SAP',
      totvs: 'TOTVS',
      custom: 'Personalizado'
    }
    return labels[type] || type
  }

  const getAuthTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      none: 'Sem autenticação',
      basic: 'Basic Auth',
      token: 'Token Bearer',
      header: 'Header personalizado'
    }
    return labels[type] || type
  }

  const getStatusBadge = (system: ExternalSystem) => {
    if (!system.is_active) {
      return <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">Inativo</span>
    }
    if (system.last_test_success === true) {
      return <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Conectado</span>
    }
    if (system.last_test_success === false) {
      return <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Erro</span>
    }
    return <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">Pendente</span>
  }

  const getFullUrl = (system: ExternalSystem) => {
    if (system.full_url) return system.full_url
    let url = system.host
    if (system.port) url += `:${system.port}`
    if (system.context_path) url += `/${system.context_path}`
    return url
  }

  if (loading) {
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Sistemas Externos</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Configure integrações com sistemas de patrimônio externos
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Novo Sistema
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Fechar</button>
        </div>
      )}

      {/* Systems List */}
      {systems.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Nenhum sistema configurado
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Configure seu primeiro sistema externo para começar a sincronizar dados de patrimônio.
          </p>
          <button
            onClick={openCreateModal}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Configurar Sistema
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {systems.map((system) => (
            <div
              key={system.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {system.name}
                    </h3>
                    {getStatusBadge(system)}
                    <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                      {getSystemTypeLabel(system.system_type)}
                    </span>
                    {system.is_default && (
                      <span className="px-2 py-1 text-xs rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                        Padrão
                      </span>
                    )}
                  </div>

                  <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                    <p>
                      <span className="font-medium">URL:</span>{' '}
                      {getFullUrl(system)}
                    </p>
                    <p>
                      <span className="font-medium">Autenticação:</span>{' '}
                      {getAuthTypeLabel(system.auth_type)}
                      {system.auth_username && ` (${system.auth_username})`}
                    </p>
                    {system.last_sync_at && (
                      <p>
                        <span className="font-medium">Última sincronização:</span>{' '}
                        {new Date(system.last_sync_at).toLocaleString('pt-BR')}
                      </p>
                    )}
                  </div>

                  {/* Test Result */}
                  {testResult?.id === system.id && (
                    <div className={`mt-3 p-3 rounded-lg text-sm ${
                      testResult.result.success
                        ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                        : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                    }`}>
                      <p className="font-medium">{testResult.result.message}</p>
                      {testResult.result.response_time_ms && testResult.result.response_time_ms > 0 && (
                        <p className="text-xs mt-1">Tempo de resposta: {testResult.result.response_time_ms}ms</p>
                      )}
                    </div>
                  )}

                  {/* Sync Result */}
                  {syncResult?.id === system.id && (
                    <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm">
                      <p className="font-medium text-blue-700 dark:text-blue-400 mb-2">Resultado da Sincronização:</p>
                      {Object.entries(syncResult.result).map(([entity, result]) => (
                        <div key={entity} className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                          <span className="capitalize">{entity}:</span>
                          <span className="text-green-600 dark:text-green-400">
                            {result.created} criados, {result.updated} atualizados
                            {result.failed > 0 && <span className="text-red-600 dark:text-red-400">, {result.failed} falhas</span>}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => handleTestConnection(system.id)}
                    disabled={testingId === system.id}
                    className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors disabled:opacity-50"
                    title="Testar Conexão"
                  >
                    {testingId === system.id ? (
                      <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    )}
                  </button>

                  <button
                    onClick={() => handleSync(system.id)}
                    disabled={syncingId === system.id || !system.is_active}
                    className="p-2 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-lg transition-colors disabled:opacity-50"
                    title="Sincronizar"
                  >
                    {syncingId === system.id ? (
                      <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    )}
                  </button>

                  <button
                    onClick={() => openEditModal(system)}
                    className="p-2 text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                    title="Editar"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>

                  <button
                    onClick={() => setDeletingId(system.id)}
                    className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    title="Excluir"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setShowModal(false)} />

            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                {editingSystem ? 'Editar Sistema' : 'Novo Sistema'}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Nome *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    placeholder="Ex: ASI Patrimônio CJF"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Tipo de Sistema *
                  </label>
                  <select
                    required
                    value={formData.system_type}
                    onChange={(e) => setFormData({ ...formData, system_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="asi">ASI Patrimônio</option>
                    <option value="sap">SAP</option>
                    <option value="totvs">TOTVS</option>
                    <option value="custom">Personalizado</option>
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Host *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.host}
                      onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                      placeholder="http://servidor.com.br"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Porta
                    </label>
                    <input
                      type="number"
                      value={formData.port || ''}
                      onChange={(e) => setFormData({ ...formData, port: e.target.value ? parseInt(e.target.value) : undefined })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                      placeholder="80"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Contexto (path)
                  </label>
                  <input
                    type="text"
                    value={formData.context_path}
                    onChange={(e) => setFormData({ ...formData, context_path: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    placeholder="Ex: cjf"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Tipo de Autenticação *
                  </label>
                  <select
                    required
                    value={formData.auth_type}
                    onChange={(e) => setFormData({ ...formData, auth_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="none">Sem autenticação</option>
                    <option value="basic">Basic Auth (usuário/senha)</option>
                    <option value="token">Token Bearer</option>
                    <option value="header">Header personalizado</option>
                  </select>
                </div>

                {formData.auth_type === 'basic' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Usuário
                      </label>
                      <input
                        type="text"
                        value={formData.auth_username}
                        onChange={(e) => setFormData({ ...formData, auth_username: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Senha {editingSystem && '(deixe vazio para manter)'}
                      </label>
                      <input
                        type="password"
                        value={formData.auth_password}
                        onChange={(e) => setFormData({ ...formData, auth_password: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                )}

                {formData.auth_type === 'token' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Token {editingSystem && '(deixe vazio para manter)'}
                    </label>
                    <input
                      type="password"
                      value={formData.auth_token}
                      onChange={(e) => setFormData({ ...formData, auth_token: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                      placeholder="Bearer token"
                    />
                  </div>
                )}

                {formData.auth_type === 'header' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Nome do Header
                      </label>
                      <input
                        type="text"
                        value={formData.auth_header_name}
                        onChange={(e) => setFormData({ ...formData, auth_header_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                        placeholder="X-API-Key"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Valor {editingSystem && '(deixe vazio para manter)'}
                      </label>
                      <input
                        type="password"
                        value={formData.auth_token}
                        onChange={(e) => setFormData({ ...formData, auth_token: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Timeout (segundos)
                    </label>
                    <input
                      type="number"
                      value={formData.timeout_seconds || 30}
                      onChange={(e) => setFormData({ ...formData, timeout_seconds: parseInt(e.target.value) || 30 })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Tentativas
                    </label>
                    <input
                      type="number"
                      value={formData.retry_attempts || 3}
                      onChange={(e) => setFormData({ ...formData, retry_attempts: parseInt(e.target.value) || 3 })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.is_default}
                      onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                      className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                    <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">Sistema padrão</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.double_json_encoding}
                      onChange={(e) => setFormData({ ...formData, double_json_encoding: e.target.checked })}
                      className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                    <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">Double JSON encoding</span>
                  </label>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                  >
                    {saving ? 'Salvando...' : 'Salvar'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setDeletingId(null)} />

            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                Confirmar Exclusão
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Tem certeza que deseja excluir este sistema? Esta ação não pode ser desfeita.
              </p>

              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setDeletingId(null)}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={() => handleDelete(deletingId)}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                >
                  Excluir
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
