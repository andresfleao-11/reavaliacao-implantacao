'use client'

import { useState, useEffect } from 'react'
import AdminRoute from '@/components/AdminRoute'

interface Client {
  id: number
  nome: string
  nome_curto: string | null
}

interface MaterialCharacteristic {
  id: number
  nome: string
  descricao: string | null
  tipo_dado: string
  opcoes_json: string[] | null
}

interface Material {
  id: number
  nome: string
  codigo: string | null
  caracteristicas?: MaterialCharacteristic[]
}

interface CharacteristicType {
  id: number
  nome: string
}

interface ItemCharacteristic {
  id: number
  tipo_id: number
  tipo_nome: string
  valor: string
}

interface Item {
  id: number
  client_id: number | null
  material_id: number
  material_nome: string
  codigo: string | null
  patrimonio: string | null
  project_id: number | null
  status: string
  localizacao: string | null
  observacoes: string | null
  caracteristicas: ItemCharacteristic[]
  created_at: string
}

interface ItemListResponse {
  items: Item[]
  total: number
  page: number
  per_page: number
}

interface StatusOption {
  value: string
  label: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const emptyItem = {
  client_id: null as number | null,
  material_id: 0,
  codigo: '',
  patrimonio: '',
  project_id: null as number | null,
  status: 'DISPONIVEL',
  localizacao: '',
  observacoes: '',
}

export default function ItensPage() {
  const [items, setItems] = useState<Item[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [characteristicTypes, setCharacteristicTypes] = useState<CharacteristicType[]>([])
  const [statusOptions, setStatusOptions] = useState<StatusOption[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterMaterialId, setFilterMaterialId] = useState('')
  const [filterClientId, setFilterClientId] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [formData, setFormData] = useState(emptyItem)
  const [formCharacteristics, setFormCharacteristics] = useState<{nome: string, valor: string}[]>([])
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const perPage = 10

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
      })
      if (search) params.append('search', search)
      if (filterMaterialId) params.append('material_id', filterMaterialId)
      if (filterClientId) params.append('client_id', filterClientId)
      if (filterStatus) params.append('status', filterStatus)

      const res = await fetch(`${API_URL}/api/materials/items/list?${params}`)
      const data: ItemListResponse = await res.json()
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error('Erro ao carregar itens:', err)
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  const fetchMaterials = async () => {
    try {
      const res = await fetch(`${API_URL}/api/materials/options/list`)
      const data = await res.json()
      setMaterials(data)
    } catch (err) {
      console.error('Erro ao carregar materiais:', err)
    }
  }

  const fetchMaterialDetails = async (materialId: number) => {
    try {
      const res = await fetch(`${API_URL}/api/materials/${materialId}`)
      const data = await res.json()
      setSelectedMaterial(data)

      // Inicializar características com base no material
      if (data.caracteristicas && data.caracteristicas.length > 0) {
        setFormCharacteristics(
          data.caracteristicas.map((c: MaterialCharacteristic) => ({
            nome: c.nome,
            valor: ''
          }))
        )
      } else {
        setFormCharacteristics([])
      }
    } catch (err) {
      console.error('Erro ao carregar detalhes do material:', err)
      setSelectedMaterial(null)
      setFormCharacteristics([])
    }
  }

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_URL}/api/clients/options/list`)
      const data = await res.json()
      setClients(data)
    } catch (err) {
      console.error('Erro ao carregar clientes:', err)
    }
  }

  const fetchCharacteristicTypes = async () => {
    try {
      const res = await fetch(`${API_URL}/api/materials/options/characteristic-types`)
      const data = await res.json()
      setCharacteristicTypes(data)
    } catch (err) {
      console.error('Erro ao carregar tipos:', err)
    }
  }

  const fetchStatusOptions = async () => {
    try {
      const res = await fetch(`${API_URL}/api/materials/items/status/options`)
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data)) {
          setStatusOptions(data)
          return
        }
      }
      // Fallback para status padrão se API não existir
      setStatusOptions([
        { value: 'DISPONIVEL', label: 'Disponível' },
        { value: 'EM_USO', label: 'Em Uso' },
        { value: 'MANUTENCAO', label: 'Manutenção' },
        { value: 'BAIXADO', label: 'Baixado' },
        { value: 'TRANSFERIDO', label: 'Transferido' },
      ])
    } catch (err) {
      console.error('Erro ao carregar status:', err)
      // Fallback para status padrão
      setStatusOptions([
        { value: 'DISPONIVEL', label: 'Disponível' },
        { value: 'EM_USO', label: 'Em Uso' },
        { value: 'MANUTENCAO', label: 'Manutenção' },
        { value: 'BAIXADO', label: 'Baixado' },
        { value: 'TRANSFERIDO', label: 'Transferido' },
      ])
    }
  }

  useEffect(() => {
    fetchMaterials()
    fetchClients()
    fetchCharacteristicTypes()
    fetchStatusOptions()
  }, [])

  useEffect(() => {
    fetchItems()
  }, [page, search, filterMaterialId, filterClientId, filterStatus])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchItems()
  }

  const openNewModal = () => {
    setEditingItem(null)
    setFormData(emptyItem)
    setFormCharacteristics([])
    setSelectedMaterial(null)
    setError('')
    setShowModal(true)
  }

  const openEditModal = (item: Item) => {
    setEditingItem(item)
    setFormData({
      material_id: item.material_id,
      codigo: item.codigo || '',
      patrimonio: item.patrimonio || '',
      project_id: item.project_id,
      status: item.status,
      localizacao: item.localizacao || '',
      observacoes: item.observacoes || '',
    })
    setFormCharacteristics(item.caracteristicas.map(c => ({
      tipo_id: c.tipo_id,
      valor: c.valor
    })))
    setError('')
    setShowModal(true)
  }

  const updateCharacteristicValue = (index: number, value: string) => {
    const updated = [...formCharacteristics]
    updated[index] = { ...updated[index], valor: value }
    setFormCharacteristics(updated)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')

    try {
      const url = editingItem
        ? `${API_URL}/api/materials/items/${editingItem.id}`
        : `${API_URL}/api/materials/items`
      const method = editingItem ? 'PUT' : 'POST'

      const payload: any = {
        ...formData,
        material_id: Number(formData.material_id),
      }

      if (!editingItem) {
        // Converter nomes de características em tipo_id
        const caracteristicasComId = formCharacteristics
          .filter(c => c.nome && c.valor)
          .map(c => {
            const tipo = characteristicTypes.find(t => t.nome === c.nome)
            if (!tipo) return null
            return { tipo_id: tipo.id, valor: c.valor }
          })
          .filter(c => c !== null)

        payload.caracteristicas = caracteristicasComId
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
      fetchItems()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (item: Item) => {
    if (!confirm(`Deseja realmente excluir o item "${item.patrimonio || item.codigo || item.id}"?`)) return

    try {
      const res = await fetch(`${API_URL}/api/materials/items/${item.id}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao excluir')
      }

      fetchItems()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      DISPONIVEL: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300',
      EM_USO: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300',
      MANUTENCAO: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300',
      BAIXADO: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300',
      TRANSFERIDO: 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300',
    }
    const option = statusOptions.find(s => s.value === status)
    return (
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 dark:bg-gray-700'}`}>
        {option?.label || status}
      </span>
    )
  }

  const totalPages = Math.ceil(total / perPage)

  return (
    <AdminRoute>
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Itens</h1>
        <button
          onClick={openNewModal}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          Novo Item
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 mb-6">
        <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por código ou patrimônio..."
            className="flex-1 min-w-[200px] px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
          <select
            value={filterMaterialId}
            onChange={(e) => { setFilterMaterialId(e.target.value); setPage(1); }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Todos os materiais</option>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>{m.nome}</option>
            ))}
          </select>
          <select
            value={filterClientId}
            onChange={(e) => { setFilterClientId(e.target.value); setPage(1); }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Todos os clientes</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.nome_curto || c.nome}</option>
            ))}
          </select>
          <select
            value={filterStatus}
            onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Todos os status</option>
            {Array.isArray(statusOptions) && statusOptions.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <button
            type="submit"
            className="px-6 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Buscar
          </button>
        </form>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Carregando...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            Nenhum item encontrado
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900 border-b dark:border-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Patrimônio/Código
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Material
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Localização
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Características
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
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900 dark:text-gray-100">
                        {item.patrimonio || item.codigo || `#${item.id}`}
                      </div>
                      {item.patrimonio && item.codigo && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">Cód: {item.codigo}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                      {item.material_nome}
                    </td>
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                      {item.localizacao || '-'}
                    </td>
                    <td className="px-6 py-4">
                      {item.caracteristicas.length > 0 ? (
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {item.caracteristicas.slice(0, 2).map((c, i) => (
                            <div key={i}>{c.tipo_nome}: {c.valor}</div>
                          ))}
                          {item.caracteristicas.length > 2 && (
                            <div className="text-gray-400 dark:text-gray-500">+{item.caracteristicas.length - 2} mais</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 dark:text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {getStatusBadge(item.status)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => openEditModal(item)}
                        className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 mr-3"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(item)}
                        className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
                      >
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="px-6 py-4 border-t dark:border-gray-700 flex items-center justify-between">
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Mostrando {(page - 1) * perPage + 1} a {Math.min(page * perPage, total)} de {total} resultados
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 border dark:border-gray-600 rounded disabled:opacity-50 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1 border dark:border-gray-600 rounded disabled:opacity-50 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    Próximo
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {editingItem ? 'Editar Item' : 'Novo Item'}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="p-6">
              {error && (
                <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Material *
                  </label>
                  <select
                    required
                    disabled={!!editingItem}
                    value={formData.material_id}
                    onChange={(e) => {
                      const materialId = Number(e.target.value)
                      setFormData({ ...formData, material_id: materialId })
                      if (materialId && !editingItem) {
                        fetchMaterialDetails(materialId)
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100 dark:disabled:bg-gray-700 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">Selecione o material...</option>
                    {materials.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.codigo ? `[${m.codigo}] ` : ''}{m.nome}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Cliente (opcional)
                  </label>
                  <select
                    value={formData.client_id || ''}
                    onChange={(e) => setFormData({
                      ...formData,
                      client_id: e.target.value ? Number(e.target.value) : null
                    })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">Nenhum cliente</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome_curto || c.nome}
                      </option>
                    ))}
                  </select>
                </div>

                {!editingItem && formCharacteristics.length > 0 && (
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Características do Material
                    </label>
                    {formCharacteristics.map((char, idx) => {
                      const materialChar = selectedMaterial?.caracteristicas?.find(c => c.nome === char.nome)
                      return (
                        <div key={idx} className="mb-3">
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                            {char.nome}
                            {materialChar?.descricao && (
                              <span className="text-gray-400 dark:text-gray-500 font-normal ml-1">
                                ({materialChar.descricao})
                              </span>
                            )}
                          </label>
                          {materialChar?.tipo_dado === 'lista' && materialChar.opcoes_json ? (
                            <select
                              value={char.valor}
                              onChange={(e) => updateCharacteristicValue(idx, e.target.value)}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            >
                              <option value="">Selecione...</option>
                              {materialChar.opcoes_json.map((opcao, i) => (
                                <option key={i} value={opcao}>{opcao}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type="text"
                              value={char.valor}
                              onChange={(e) => updateCharacteristicValue(idx, e.target.value)}
                              placeholder={`Informe ${char.nome.toLowerCase()}`}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            />
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
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
    </AdminRoute>
  )
}
