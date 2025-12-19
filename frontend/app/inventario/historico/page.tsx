'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { API_URL } from '@/lib/api'
import Link from 'next/link'

interface RfidBatch {
  id: number
  batch_id: string
  device_id: string
  location: string | null
  tag_count: number
  created_at: string
  project_id: number | null
}

interface RfidTag {
  id: number
  epc: string
  rssi: string | null
  read_at: string
  matched: boolean
  item_id: number | null
}

interface BatchDetail extends RfidBatch {
  tags: RfidTag[]
}

interface Stats {
  total_batches: number
  total_tags: number
  matched_tags: number
  unmatched_tags: number
  unique_epcs: number
}

export default function HistoricoInventarioPage() {
  const { user } = useAuth()
  const [batches, setBatches] = useState<RfidBatch[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Carregar lotes
  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    const token = localStorage.getItem('token')

    try {
      // Buscar lotes e estatísticas em paralelo
      const [batchesRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/rfid/batches?limit=50`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`${API_URL}/api/rfid/stats`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ])

      if (batchesRes.ok) {
        const batchesData = await batchesRes.json()
        setBatches(batchesData)
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats(statsData)
      }
    } catch (err) {
      console.error('Erro ao carregar dados:', err)
    } finally {
      setLoading(false)
    }
  }

  // Carregar detalhes do lote
  const loadBatchDetail = async (batchId: string) => {
    setLoadingDetail(true)
    const token = localStorage.getItem('token')

    try {
      const res = await fetch(`${API_URL}/api/rfid/batches/${batchId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        const data = await res.json()
        setSelectedBatch(data)
      }
    } catch (err) {
      console.error('Erro ao carregar detalhes:', err)
    } finally {
      setLoadingDetail(false)
    }
  }

  // Excluir lote
  const deleteBatch = async (batchId: string) => {
    if (!confirm('Deseja excluir este lote e todas as suas tags?')) return

    const token = localStorage.getItem('token')

    try {
      const res = await fetch(`${API_URL}/api/rfid/batches/${batchId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (res.ok) {
        setBatches(prev => prev.filter(b => b.batch_id !== batchId))
        if (selectedBatch?.batch_id === batchId) {
          setSelectedBatch(null)
        }
        fetchData() // Recarregar estatísticas
      }
    } catch (err) {
      console.error('Erro ao excluir:', err)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('pt-BR')
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
          Histórico de Leituras RFID
        </h1>
        <Link href="/inventario" className="btn-primary text-sm">
          Nova Leitura
        </Link>
      </div>

      {/* Estatísticas */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="card text-center">
            <p className="text-2xl font-bold text-primary-600 dark:text-primary-400">
              {stats.total_batches}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">Lotes</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-primary-600 dark:text-primary-400">
              {stats.total_tags}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">Tags Lidas</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.matched_tags}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">Vinculadas</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
              {stats.unique_epcs}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">EPCs Únicos</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Lista de lotes */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Lotes de Leitura
          </h2>

          {loading ? (
            <div className="flex justify-center py-8">
              <svg className="animate-spin w-8 h-8 text-primary-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : batches.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p>Nenhuma leitura registrada</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {batches.map((batch) => (
                <div
                  key={batch.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedBatch?.batch_id === batch.batch_id
                      ? 'bg-primary-50 dark:bg-primary-900/20 border-primary-300 dark:border-primary-700'
                      : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                  onClick={() => loadBatchDetail(batch.batch_id)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {batch.device_id}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {formatDate(batch.created_at)}
                      </p>
                      {batch.location && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          Local: {batch.location}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">
                        {batch.tag_count} tags
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteBatch(batch.batch_id)
                        }}
                        className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detalhes do lote */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Detalhes do Lote
          </h2>

          {loadingDetail ? (
            <div className="flex justify-center py-8">
              <svg className="animate-spin w-8 h-8 text-primary-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : selectedBatch ? (
            <div>
              <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  <strong>ID:</strong> {selectedBatch.batch_id}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  <strong>Dispositivo:</strong> {selectedBatch.device_id}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  <strong>Data:</strong> {formatDate(selectedBatch.created_at)}
                </p>
                {selectedBatch.location && (
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    <strong>Local:</strong> {selectedBatch.location}
                  </p>
                )}
              </div>

              <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-2">
                Tags ({selectedBatch.tags?.length || 0})
              </h3>

              <div className="space-y-2 max-h-[350px] overflow-y-auto">
                {selectedBatch.tags?.map((tag) => (
                  <div
                    key={tag.id}
                    className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded"
                  >
                    <div>
                      <p className="font-mono text-sm text-gray-900 dark:text-gray-100">
                        {tag.epc}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        RSSI: {tag.rssi || 'N/A'} | {new Date(tag.read_at).toLocaleTimeString()}
                      </p>
                    </div>
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      tag.matched
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                    }`}>
                      {tag.matched ? 'Vinculada' : 'Pendente'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
              </svg>
              <p>Selecione um lote para ver os detalhes</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
