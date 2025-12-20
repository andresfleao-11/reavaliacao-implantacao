'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { externalSystemsApi, inventorySessionsApi, ExternalSystem, InventorySession, MasterDataItem } from '@/lib/api'

export default function BensCadastradosPage() {
  const [externalSystems, setExternalSystems] = useState<ExternalSystem[]>([])
  const [sessions, setSessions] = useState<InventorySession[]>([])
  const [selectedSystem, setSelectedSystem] = useState<ExternalSystem | null>(null)
  const [ugs, setUgs] = useState<MasterDataItem[]>([])
  const [uls, setUls] = useState<MasterDataItem[]>([])
  const [selectedUg, setSelectedUg] = useState<MasterDataItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingData, setLoadingData] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadInitialData()
  }, [])

  const loadInitialData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [systemsData, sessionsData] = await Promise.all([
        externalSystemsApi.list(),
        inventorySessionsApi.list({ limit: 5 })
      ])

      setExternalSystems(systemsData.filter(s => s.is_active))
      setSessions(sessionsData.items)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar dados')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectSystem = async (system: ExternalSystem) => {
    setSelectedSystem(system)
    setSelectedUg(null)
    setUls([])
    setLoadingData(true)

    try {
      const data = await externalSystemsApi.getUGs(system.id)
      setUgs(data)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar UGs')
    } finally {
      setLoadingData(false)
    }
  }

  const handleSelectUg = async (ug: MasterDataItem) => {
    setSelectedUg(ug)
    setLoadingData(true)

    try {
      const data = await externalSystemsApi.getULs(selectedSystem!.id, ug.id)
      setUls(data)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar ULs')
    } finally {
      setLoadingData(false)
    }
  }

  const getTotalStats = () => {
    let totalExpected = 0
    let totalFound = 0

    sessions.forEach(session => {
      if (session.statistics) {
        totalExpected += session.statistics.total_expected
        totalFound += session.statistics.total_found
      }
    })

    return { totalExpected, totalFound }
  }

  const stats = getTotalStats()

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
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Bens Cadastrados</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Visualize os bens patrimoniais sincronizados dos sistemas externos
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Fechar</button>
        </div>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">Sistemas Configurados</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{externalSystems.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">Bens Esperados (Sessões)</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.totalExpected}</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
              <svg className="w-6 h-6 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">Bens Encontrados</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.totalFound}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* External Systems */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="font-semibold text-gray-900 dark:text-white">Sistemas Externos</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Selecione um sistema para visualizar as estruturas sincronizadas
            </p>
          </div>

          {externalSystems.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Nenhum sistema externo configurado
              </p>
              <Link
                href="/configuracoes/sistemas-externos"
                className="text-primary-600 hover:text-primary-700"
              >
                Configurar Sistema
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {externalSystems.map((system) => (
                <button
                  key={system.id}
                  onClick={() => handleSelectSystem(system)}
                  className={`w-full p-4 text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors ${
                    selectedSystem?.id === system.id ? 'bg-primary-50 dark:bg-primary-900/20' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">{system.name}</p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {system.host}
                        {system.port && `:${system.port}`}
                        {system.context_path && `/${system.context_path}`}
                      </p>
                    </div>
                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Master Data Viewer */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="font-semibold text-gray-900 dark:text-white">
              {selectedSystem ? `Estrutura: ${selectedSystem.name}` : 'Estrutura Organizacional'}
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {selectedSystem ? 'UGs e ULs sincronizadas' : 'Selecione um sistema para visualizar'}
            </p>
          </div>

          {loadingData ? (
            <div className="p-8 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-600"></div>
            </div>
          ) : !selectedSystem ? (
            <div className="p-8 text-center text-gray-600 dark:text-gray-400">
              Selecione um sistema externo para visualizar a estrutura
            </div>
          ) : (
            <div className="p-4 space-y-4 max-h-[400px] overflow-y-auto">
              {/* UGs */}
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">
                  Unidades Gestoras ({ugs.length})
                </p>
                {ugs.length === 0 ? (
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Nenhuma UG sincronizada. Execute a sincronização no sistema externo.
                  </p>
                ) : (
                  <div className="space-y-1">
                    {ugs.map((ug) => (
                      <button
                        key={ug.id}
                        onClick={() => handleSelectUg(ug)}
                        className={`w-full p-2 text-left text-sm rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                          selectedUg?.id === ug.id ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400' : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        <span className="font-medium">{ug.code}</span> - {ug.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* ULs */}
              {selectedUg && (
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">
                    Unidades Locais - {selectedUg.name} ({uls.length})
                  </p>
                  {uls.length === 0 ? (
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Nenhuma UL encontrada para esta UG
                    </p>
                  ) : (
                    <div className="space-y-1">
                      {uls.map((ul) => (
                        <div
                          key={ul.id}
                          className="p-2 text-sm text-gray-700 dark:text-gray-300 rounded-lg bg-gray-50 dark:bg-gray-700"
                        >
                          <span className="font-medium">{ul.code}</span> - {ul.name}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Recent Sessions */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">Sessões Recentes</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Acesse as sessões para gerenciar os bens esperados e leituras
            </p>
          </div>
          <Link
            href="/inventario/sessoes"
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            Ver todas
          </Link>
        </div>

        {sessions.length === 0 ? (
          <div className="p-8 text-center text-gray-600 dark:text-gray-400">
            Nenhuma sessão de inventário encontrada
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {sessions.map((session) => (
              <Link
                key={session.id}
                href={`/inventario/sessoes/${session.id}`}
                className="block p-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {session.name || session.code}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {session.statistics
                        ? `${session.statistics.total_found} de ${session.statistics.total_expected} bens encontrados`
                        : 'Sem estatísticas'}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      session.status === 'completed'
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                        : session.status === 'in_progress'
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                    }`}>
                      {session.status === 'completed' ? 'Concluída' :
                        session.status === 'in_progress' ? 'Em andamento' :
                          session.status === 'paused' ? 'Pausada' : 'Rascunho'}
                    </span>
                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Info Card */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <h3 className="font-medium text-blue-800 dark:text-blue-300">Sobre os Bens Cadastrados</h3>
            <p className="text-sm text-blue-700 dark:text-blue-400 mt-1">
              Os bens patrimoniais são sincronizados dos sistemas externos configurados. Para gerenciar os bens
              de uma sessão específica, acesse a sessão e visualize os bens esperados. As leituras de RFID
              atualizam automaticamente o status de verificação dos bens.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
