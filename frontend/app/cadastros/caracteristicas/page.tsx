'use client'

import { useState, useEffect } from 'react'

interface CharacteristicType {
  id: number
  nome: string
  descricao: string | null
  escopo: string
  tipo_dado: string
  tipo_material_especifico: string | null
  valor_unico: boolean
  ativo: boolean
  created_at: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const emptyType = {
  nome: '',
  descricao: '',
  escopo: 'GENERICA',
  tipo_dado: 'texto',
  tipo_material_especifico: '',
  valor_unico: false,
}

const escopos = [
  { value: 'GENERICA', label: 'Genérica (qualquer material)' },
  { value: 'ESPECIFICA', label: 'Específica (tipo de material)' },
]

const tiposDado = [
  { value: 'texto', label: 'Texto' },
  { value: 'numero', label: 'Número' },
  { value: 'data', label: 'Data' },
  { value: 'lista', label: 'Lista de opções' },
]

export default function CaracteristicasPage() {
  const [types, setTypes] = useState<CharacteristicType[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingType, setEditingType] = useState<CharacteristicType | null>(null)
  const [formData, setFormData] = useState(emptyType)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const fetchTypes = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/materials/characteristic-types`)
      if (!res.ok) {
        console.error('Erro na resposta:', res.status)
        setTypes([])
        return
      }
      const data = await res.json()
      if (Array.isArray(data)) {
        setTypes(data)
      } else {
        console.error('Resposta não é um array:', data)
        setTypes([])
      }
    } catch (err) {
      console.error('Erro ao carregar tipos:', err)
      setTypes([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTypes()
  }, [])

  const openNewModal = () => {
    setEditingType(null)
    setFormData(emptyType)
    setError('')
    setShowModal(true)
  }

  const openEditModal = (type: CharacteristicType) => {
    setEditingType(type)
    setFormData({
      nome: type.nome,
      descricao: type.descricao || '',
      escopo: type.escopo,
      tipo_dado: type.tipo_dado,
      tipo_material_especifico: type.tipo_material_especifico || '',
      valor_unico: type.valor_unico,
    })
    setError('')
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')

    try {
      const url = editingType
        ? `${API_URL}/api/materials/characteristic-types/${editingType.id}`
        : `${API_URL}/api/materials/characteristic-types`
      const method = editingType ? 'PUT' : 'POST'

      const payload = {
        ...formData,
        tipo_material_especifico: formData.escopo === 'ESPECIFICA' ? formData.tipo_material_especifico : null,
      }

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao salvar')
      }

      setShowModal(false)
      fetchTypes()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (type: CharacteristicType) => {
    if (!confirm(`Deseja realmente excluir o tipo "${type.nome}"?`)) return

    try {
      const res = await fetch(`${API_URL}/api/materials/characteristic-types/${type.id}`, {
        method: 'DELETE',
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Erro ao excluir')
      }

      alert(data.message)
      fetchTypes()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Tipos de Características</h1>
        <button
          onClick={openNewModal}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          Novo Tipo
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Carregando...</div>
        ) : types.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            Nenhum tipo de característica cadastrado
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-900 border-b dark:border-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Nome
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Escopo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Tipo de Dado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Valor Único
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {types.map((type) => (
                <tr key={type.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{type.nome}</div>
                    {type.descricao && (
                      <div className="text-sm text-gray-500 dark:text-gray-400">{type.descricao}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                    <span className={`px-2 py-1 rounded text-xs ${
                      type.escopo === 'GENERICA' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300' : 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300'
                    }`}>
                      {type.escopo === 'GENERICA' ? 'Genérica' : 'Específica'}
                    </span>
                    {type.tipo_material_especifico && (
                      <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">({type.tipo_material_especifico})</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                    {tiposDado.find(t => t.value === type.tipo_dado)?.label || type.tipo_dado}
                  </td>
                  <td className="px-6 py-4">
                    {type.valor_unico ? (
                      <span className="text-green-600 dark:text-green-400">Sim</span>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-500">Não</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs ${
                      type.ativo ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                    }`}>
                      {type.ativo ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => openEditModal(type)}
                      className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 mr-3"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => handleDelete(type)}
                      className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
            <div className="p-6 border-b dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {editingType ? 'Editar Tipo de Característica' : 'Novo Tipo de Característica'}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="p-6">
              {error && (
                <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg">
                  {error}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Nome *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.nome}
                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                    placeholder="Ex: Número de Série, Processador, Capacidade BTU"
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Descrição
                  </label>
                  <textarea
                    value={formData.descricao}
                    onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Escopo
                  </label>
                  <select
                    value={formData.escopo}
                    onChange={(e) => setFormData({ ...formData, escopo: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    {escopos.map((e) => (
                      <option key={e.value} value={e.value}>{e.label}</option>
                    ))}
                  </select>
                </div>

                {formData.escopo === 'ESPECIFICA' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Tipo de Material
                    </label>
                    <input
                      type="text"
                      value={formData.tipo_material_especifico}
                      onChange={(e) => setFormData({ ...formData, tipo_material_especifico: e.target.value })}
                      placeholder="Ex: NOTEBOOK, AR_CONDICIONADO"
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Essa característica só aparecerá para materiais deste tipo
                    </p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Tipo de Dado
                  </label>
                  <select
                    value={formData.tipo_dado}
                    onChange={(e) => setFormData({ ...formData, tipo_dado: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    {tiposDado.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="valor_unico"
                    checked={formData.valor_unico}
                    onChange={(e) => setFormData({ ...formData, valor_unico: e.target.checked })}
                    className="w-4 h-4 text-primary-600 border-gray-300 dark:border-gray-600 rounded focus:ring-primary-500"
                  />
                  <label htmlFor="valor_unico" className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                    Valor único por item (ex: número de série)
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6 pt-4 border-t dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
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
      )}
    </div>
  )
}
