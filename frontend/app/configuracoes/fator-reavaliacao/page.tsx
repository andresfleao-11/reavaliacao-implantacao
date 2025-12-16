'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface RevaluationParams {
  ec_map: Record<string, number>
  pu_map: Record<string, number>
  vuf_map: Record<string, number>
  weights: Record<string, number>
}

const defaultEcMap = { 'OTIMO': 1.0, 'BOM': 0.8, 'REGULAR': 0.6, 'RUIM': 0.4 }
const defaultPuMap = { '0-2': 1.0, '2-5': 0.85, '5-10': 0.7, '>10': 0.5 }
const defaultVufMap = { '>5': 1.0, '3-5': 0.8, '1-3': 0.6, '<1': 0.4 }
const defaultWeights = { 'ec': 0.4, 'pu': 0.3, 'vuf': 0.3 }

export default function FatorReavaliacaoPage() {
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Form state para fator de reavaliacao
  const [ecMap, setEcMap] = useState<Record<string, number>>(defaultEcMap)
  const [puMap, setPuMap] = useState<Record<string, number>>(defaultPuMap)
  const [vufMap, setVufMap] = useState<Record<string, number>>(defaultVufMap)
  const [weights, setWeights] = useState<Record<string, number>>(defaultWeights)

  // Carregar parametros existentes
  useEffect(() => {
    const fetchParams = async () => {
      try {
        const token = localStorage.getItem('token')
        const response = await fetch(`${API_URL}/api/settings/revaluation`, {
          headers: { Authorization: `Bearer ${token}` }
        })

        if (response.ok) {
          const data: RevaluationParams = await response.json()
          if (data.ec_map) setEcMap(data.ec_map)
          if (data.pu_map) setPuMap(data.pu_map)
          if (data.vuf_map) setVufMap(data.vuf_map)
          if (data.weights) setWeights(data.weights)
        }
      } catch (err) {
        console.error('Erro ao carregar parametros:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchParams()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`${API_URL}/api/settings/revaluation`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          ec_map: ecMap,
          pu_map: puMap,
          vuf_map: vufMap,
          weights: weights
        })
      })

      if (response.ok) {
        setSuccess('Parametros salvos com sucesso!')
        setTimeout(() => setSuccess(''), 3000)
      } else {
        const data = await response.json()
        setError(data.detail || 'Erro ao salvar parametros')
      }
    } catch (err) {
      setError('Erro de conexao')
    } finally {
      setSaving(false)
    }
  }

  const resetToDefaults = () => {
    setEcMap(defaultEcMap)
    setPuMap(defaultPuMap)
    setVufMap(defaultVufMap)
    setWeights(defaultWeights)
  }

  // Adicionar nova chave aos maps
  const addEcKey = () => {
    const key = prompt('Nome da nova categoria de Estado de Conservacao:')
    if (key && !ecMap[key]) {
      setEcMap({ ...ecMap, [key]: 0.5 })
    }
  }

  const addPuKey = () => {
    const key = prompt('Faixa do Periodo de Utilizacao (ex: 10-15):')
    if (key && !puMap[key]) {
      setPuMap({ ...puMap, [key]: 0.5 })
    }
  }

  const addVufKey = () => {
    const key = prompt('Faixa da Vida Util Futura (ex: 0-1):')
    if (key && !vufMap[key]) {
      setVufMap({ ...vufMap, [key]: 0.5 })
    }
  }

  // Remover chave dos maps
  const removeEcKey = (key: string) => {
    const newMap = { ...ecMap }
    delete newMap[key]
    setEcMap(newMap)
  }

  const removePuKey = (key: string) => {
    const newMap = { ...puMap }
    delete newMap[key]
    setPuMap(newMap)
  }

  const removeVufKey = (key: string) => {
    const newMap = { ...vufMap }
    delete newMap[key]
    setVufMap(newMap)
  }

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-8">Fator de Reavaliacao</h1>
        <div className="card flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  const weightsSum = Object.values(weights).reduce((sum, val) => sum + val, 0)

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Fator de Reavaliacao</h1>
        <div className="flex gap-2">
          <button
            onClick={resetToDefaults}
            className="btn-secondary"
          >
            Restaurar Padroes
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary"
          >
            {saving ? 'Salvando...' : 'Salvar Alteracoes'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {success && (
        <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <p className="text-green-700 dark:text-green-300">{success}</p>
        </div>
      )}

      <div className="card mb-6">
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Configure os fatores globais para calculo do valor de reavaliacao baseado em Estado de Conservacao (EC),
          Periodo de Utilizacao (PU) e Vida Util Futura (VUF). Estes valores serao usados como padrao para novos projetos.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Estado de Conservacao */}
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
            <div className="flex justify-between items-center mb-3">
              <h4 className="font-medium text-gray-700 dark:text-gray-300">Estado de Conservacao (EC)</h4>
              <button
                onClick={addEcKey}
                className="text-xs text-primary-600 hover:text-primary-800 dark:text-primary-400"
              >
                + Adicionar
              </button>
            </div>
            <div className="space-y-2">
              {Object.entries(ecMap).map(([key, value]) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{key}</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={value}
                    onChange={(e) => setEcMap({ ...ecMap, [key]: Number(e.target.value) })}
                    className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <button
                    onClick={() => removeEcKey(key)}
                    className="text-red-500 hover:text-red-700 text-xs"
                    title="Remover"
                  >
                    X
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Periodo de Utilizacao */}
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
            <div className="flex justify-between items-center mb-3">
              <h4 className="font-medium text-gray-700 dark:text-gray-300">Periodo de Utilizacao (PU)</h4>
              <button
                onClick={addPuKey}
                className="text-xs text-primary-600 hover:text-primary-800 dark:text-primary-400"
              >
                + Adicionar
              </button>
            </div>
            <div className="space-y-2">
              {Object.entries(puMap).map(([key, value]) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{key} anos</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={value}
                    onChange={(e) => setPuMap({ ...puMap, [key]: Number(e.target.value) })}
                    className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <button
                    onClick={() => removePuKey(key)}
                    className="text-red-500 hover:text-red-700 text-xs"
                    title="Remover"
                  >
                    X
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Vida Util Futura */}
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
            <div className="flex justify-between items-center mb-3">
              <h4 className="font-medium text-gray-700 dark:text-gray-300">Vida Util Futura (VUF)</h4>
              <button
                onClick={addVufKey}
                className="text-xs text-primary-600 hover:text-primary-800 dark:text-primary-400"
              >
                + Adicionar
              </button>
            </div>
            <div className="space-y-2">
              {Object.entries(vufMap).map(([key, value]) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{key} anos</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={value}
                    onChange={(e) => setVufMap({ ...vufMap, [key]: Number(e.target.value) })}
                    className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <button
                    onClick={() => removeVufKey(key)}
                    className="text-red-500 hover:text-red-700 text-xs"
                    title="Remover"
                  >
                    X
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Pesos */}
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
            <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-3">Pesos dos Fatores</h4>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">A soma dos pesos deve ser 1.0</p>
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <span className="w-24 text-sm text-gray-600 dark:text-gray-400">EC</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  value={weights.ec || 0}
                  onChange={(e) => setWeights({ ...weights, ec: Number(e.target.value) })}
                  className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div className="flex items-center gap-3">
                <span className="w-24 text-sm text-gray-600 dark:text-gray-400">PU</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  value={weights.pu || 0}
                  onChange={(e) => setWeights({ ...weights, pu: Number(e.target.value) })}
                  className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div className="flex items-center gap-3">
                <span className="w-24 text-sm text-gray-600 dark:text-gray-400">VUF</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  value={weights.vuf || 0}
                  onChange={(e) => setWeights({ ...weights, vuf: Number(e.target.value) })}
                  className="flex-1 px-3 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                Soma: {weightsSum.toFixed(1)}
                {Math.abs(weightsSum - 1) > 0.01 && (
                  <span className="text-red-500 dark:text-red-400 ml-2">(deve ser 1.0)</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Informacoes adicionais */}
      <div className="card bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
        <h3 className="font-medium text-blue-800 dark:text-blue-300 mb-2">Como funciona o calculo</h3>
        <p className="text-sm text-blue-700 dark:text-blue-400 mb-3">
          O fator de reavaliacao e calculado pela formula:
        </p>
        <div className="bg-white dark:bg-gray-800 p-3 rounded font-mono text-sm text-gray-800 dark:text-gray-200">
          Fator = (EC_valor * Peso_EC) + (PU_valor * Peso_PU) + (VUF_valor * Peso_VUF)
        </div>
        <p className="text-sm text-blue-700 dark:text-blue-400 mt-3">
          Onde EC_valor, PU_valor e VUF_valor sao os valores configurados para cada categoria do bem avaliado.
        </p>
      </div>
    </div>
  )
}
