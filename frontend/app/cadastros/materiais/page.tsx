'use client'

import { useState, useEffect, useRef } from 'react'
import AdminRoute from '@/components/AdminRoute'
import { API_URL } from '@/lib/api'

interface Characteristic {
  id: number
  nome: string
  descricao: string | null
  tipo_dado: string
  opcoes: string[] | null
  created_at: string
}

interface Client {
  id: number
  nome: string
  nome_curto: string | null
}

interface Material {
  id: number
  nome: string
  descricao: string | null
  client_id: number | null
  codigo: string | null
  ativo: boolean
  caracteristicas: Characteristic[]
  created_at: string
}

interface MaterialListResponse {
  items: Material[]
  total: number
  page: number
  per_page: number
}

const tiposDado = [
  { value: 'texto', label: 'Texto' },
  { value: 'numero', label: 'Número' },
  { value: 'data', label: 'Data' },
  { value: 'lista', label: 'Lista de opções' },
]

export default function MateriaisPage() {
  const [materials, setMaterials] = useState<Material[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterClientId, setFilterClientId] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  // Modal de Material
  const [showMaterialModal, setShowMaterialModal] = useState(false)
  const [editingMaterial, setEditingMaterial] = useState<Material | null>(null)
  const [materialForm, setMaterialForm] = useState({
    nome: '',
    descricao: '',
    client_id: null as number | null,
    codigo: ''
  })

  // Modal de Características
  const [showCharModal, setShowCharModal] = useState(false)
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null)
  const [editingChar, setEditingChar] = useState<Characteristic | null>(null)
  const [charForm, setCharForm] = useState({ nome: '', descricao: '', tipo_dado: 'texto', opcoes: '' })

  // Import
  const [showImportModal, setShowImportModal] = useState(false)
  const [importResult, setImportResult] = useState<{created: number, updated: number, skipped: number, errors: string[]} | null>(null)
  const [importClientId, setImportClientId] = useState<number | null>(null)
  const [uploading, setUploading] = useState(false)
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const perPage = 10

  const fetchMaterials = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
      })
      if (search) params.append('search', search)
      if (filterClientId) params.append('client_id', filterClientId)

      const res = await fetch(`${API_URL}/api/materials?${params}`)
      const data: MaterialListResponse = await res.json()
      setMaterials(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error('Erro ao carregar materiais:', err)
      setMaterials([])
    } finally {
      setLoading(false)
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

  useEffect(() => {
    fetchClients()
  }, [])

  useEffect(() => {
    fetchMaterials()
  }, [page, search, filterClientId])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchMaterials()
  }

  // ========== MATERIAL CRUD ==========
  const openNewMaterialModal = () => {
    setEditingMaterial(null)
    setMaterialForm({ nome: '', descricao: '', client_id: null, codigo: '' })
    setError('')
    setShowMaterialModal(true)
  }

  const openEditMaterialModal = (material: Material) => {
    setEditingMaterial(material)
    setMaterialForm({
      nome: material.nome,
      descricao: material.descricao || '',
      client_id: material.client_id,
      codigo: material.codigo || ''
    })
    setError('')
    setShowMaterialModal(true)
  }

  const handleMaterialSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')

    try {
      const url = editingMaterial
        ? `${API_URL}/api/materials/${editingMaterial.id}`
        : `${API_URL}/api/materials`
      const method = editingMaterial ? 'PUT' : 'POST'

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(materialForm),
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao salvar')
      }

      setShowMaterialModal(false)
      fetchMaterials()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteMaterial = async (material: Material) => {
    if (!confirm(`Deseja realmente excluir o material "${material.nome}"?`)) return

    try {
      const res = await fetch(`${API_URL}/api/materials/${material.id}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao excluir')
      }

      fetchMaterials()
    } catch (err: any) {
      alert(err.message)
    }
  }

  // ========== CHARACTERISTICS CRUD ==========
  const openCharacteristicsModal = (material: Material) => {
    setSelectedMaterial(material)
    setEditingChar(null)
    setCharForm({ nome: '', descricao: '', tipo_dado: 'texto', opcoes: '' })
    setError('')
    setShowCharModal(true)
  }

  const openEditCharModal = (char: Characteristic) => {
    setEditingChar(char)
    setCharForm({
      nome: char.nome,
      descricao: char.descricao || '',
      tipo_dado: char.tipo_dado,
      opcoes: char.opcoes?.join(', ') || '',
    })
    setError('')
  }

  const handleCharSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedMaterial) return

    setSaving(true)
    setError('')

    try {
      const url = editingChar
        ? `${API_URL}/api/materials/${selectedMaterial.id}/characteristics/${editingChar.id}`
        : `${API_URL}/api/materials/${selectedMaterial.id}/characteristics`
      const method = editingChar ? 'PUT' : 'POST'

      // Converte string de opções para array
      const opcoesArray = charForm.opcoes
        ? charForm.opcoes.split(',').map(o => o.trim()).filter(o => o)
        : null

      const payload = {
        nome: charForm.nome,
        descricao: charForm.descricao,
        tipo_dado: charForm.tipo_dado,
        opcoes: charForm.tipo_dado === 'lista' ? opcoesArray : null,
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

      // Atualiza a lista de materiais para refletir as novas características
      fetchMaterials()

      // Limpa o formulário para adicionar outra
      setEditingChar(null)
      setCharForm({ nome: '', descricao: '', tipo_dado: 'texto', opcoes: '' })

      // Atualiza o material selecionado
      const updatedRes = await fetch(`${API_URL}/api/materials/${selectedMaterial.id}`)
      const updatedMaterial = await updatedRes.json()
      setSelectedMaterial(updatedMaterial)

    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteChar = async (char: Characteristic) => {
    if (!selectedMaterial) return
    if (!confirm(`Deseja realmente excluir a característica "${char.nome}"?`)) return

    try {
      const res = await fetch(`${API_URL}/api/materials/${selectedMaterial.id}/characteristics/${char.id}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao excluir')
      }

      // Atualiza o material selecionado
      const updatedRes = await fetch(`${API_URL}/api/materials/${selectedMaterial.id}`)
      const updatedMaterial = await updatedRes.json()
      setSelectedMaterial(updatedMaterial)
      fetchMaterials()
    } catch (err: any) {
      alert(err.message)
    }
  }

  // ========== IMPORT ==========
  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setSelectedFileName(file.name)
    setUploading(true)
    setImportResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const url = importClientId
        ? `${API_URL}/api/materials/import?client_id=${importClientId}`
        : `${API_URL}/api/materials/import`

      const res = await fetch(url, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        throw new Error(`Erro no upload: ${res.statusText}`)
      }

      const data = await res.json()
      setImportResult(data)
      fetchMaterials()
    } catch (err: any) {
      setImportResult({ created: 0, updated: 0, skipped: 0, errors: [err.message] })
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const totalPages = Math.ceil(total / perPage)

  return (
    <AdminRoute>
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Materiais e Características</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowImportModal(true)}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Importar CSV/XLSX
          </button>
          <button
            onClick={openNewMaterialModal}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Novo Material
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 mb-6">
        <form onSubmit={handleSearch} className="flex gap-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome ou código..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
          <select
            value={filterClientId}
            onChange={(e) => { setFilterClientId(e.target.value); setPage(1); }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Todos os clientes</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome_curto || c.nome}
              </option>
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
        ) : materials.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            Nenhum material encontrado
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900 border-b dark:border-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Código
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Material
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Características
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {materials.map((material) => (
                  <tr key={material.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4">
                      <div className="font-mono text-sm text-gray-900 dark:text-gray-100">
                        {material.codigo || '-'}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{material.nome}</div>
                      {material.descricao && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">{material.descricao}</div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => openCharacteristicsModal(material)}
                        className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800/40 transition-colors"
                      >
                        {material.caracteristicas?.length || 0} características
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => openEditMaterialModal(material)}
                        className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 mr-3"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDeleteMaterial(material)}
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

      {/* Modal de Material */}
      {showMaterialModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {editingMaterial ? 'Editar Material' : 'Novo Material'}
              </h2>
            </div>

            <form onSubmit={handleMaterialSubmit} className="p-6">
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
                    value={materialForm.nome}
                    onChange={(e) => setMaterialForm({ ...materialForm, nome: e.target.value })}
                    placeholder="Ex: Notebook, Ar Condicionado, Mesa..."
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Descrição
                  </label>
                  <textarea
                    value={materialForm.descricao}
                    onChange={(e) => setMaterialForm({ ...materialForm, descricao: e.target.value })}
                    rows={3}
                    placeholder="Descrição opcional do material..."
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Cliente
                  </label>
                  <select
                    value={materialForm.client_id || ''}
                    onChange={(e) => setMaterialForm({
                      ...materialForm,
                      client_id: e.target.value ? Number(e.target.value) : null
                    })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">Selecione um cliente...</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome_curto || c.nome}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Código (9 dígitos)
                  </label>
                  <input
                    type="text"
                    maxLength={9}
                    pattern="[0-9]{9}"
                    value={materialForm.codigo}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '')
                      setMaterialForm({ ...materialForm, codigo: value })
                    }}
                    placeholder="000000000"
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6 pt-4 border-t dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => setShowMaterialModal(false)}
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

      {/* Modal de Características */}
      {showCharModal && selectedMaterial && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                Características: {selectedMaterial.nome}
              </h2>
            </div>

            <div className="p-6">
              {error && (
                <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg">
                  {error}
                </div>
              )}

              {/* Lista de características existentes */}
              {selectedMaterial.caracteristicas && selectedMaterial.caracteristicas.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Características cadastradas</h3>
                  <div className="space-y-2">
                    {selectedMaterial.caracteristicas.map((char) => (
                      <div key={char.id} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                        <div>
                          <span className="font-medium text-gray-900 dark:text-gray-100">{char.nome}</span>
                          <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                            ({tiposDado.find(t => t.value === char.tipo_dado)?.label || char.tipo_dado})
                          </span>
                          {char.descricao && (
                            <p className="text-sm text-gray-500 dark:text-gray-400">{char.descricao}</p>
                          )}
                          {char.opcoes && char.opcoes.length > 0 && (
                            <p className="text-xs text-primary-600 dark:text-primary-400 mt-1">
                              Opções: {char.opcoes.join(', ')}
                            </p>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => openEditCharModal(char)}
                            className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 text-sm"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() => handleDeleteChar(char)}
                            className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-sm"
                          >
                            Excluir
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Formulário para adicionar/editar característica */}
              <form onSubmit={handleCharSubmit}>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  {editingChar ? 'Editar característica' : 'Adicionar nova característica'}
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Nome *
                    </label>
                    <input
                      type="text"
                      required
                      value={charForm.nome}
                      onChange={(e) => setCharForm({ ...charForm, nome: e.target.value })}
                      placeholder="Ex: Número de Série, Processador, Capacidade BTU..."
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Tipo de Dado
                    </label>
                    <select
                      value={charForm.tipo_dado}
                      onChange={(e) => setCharForm({ ...charForm, tipo_dado: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    >
                      {tiposDado.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Descrição
                    </label>
                    <input
                      type="text"
                      value={charForm.descricao}
                      onChange={(e) => setCharForm({ ...charForm, descricao: e.target.value })}
                      placeholder="Descrição opcional..."
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>

                  {charForm.tipo_dado === 'lista' && (
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Opções (separadas por vírgula)
                      </label>
                      <input
                        type="text"
                        value={charForm.opcoes}
                        onChange={(e) => setCharForm({ ...charForm, opcoes: e.target.value })}
                        placeholder="Ex: Dell, Lenovo, HP, Asus"
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Digite as opções separadas por vírgula. Ex: Dell, Lenovo, HP
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex justify-end gap-2 mt-4">
                  {editingChar && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditingChar(null)
                        setCharForm({ nome: '', descricao: '', tipo_dado: 'texto', opcoes: '' })
                      }}
                      className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                    >
                      Cancelar edição
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                  >
                    {saving ? 'Salvando...' : editingChar ? 'Atualizar' : 'Adicionar'}
                  </button>
                </div>
              </form>
            </div>

            <div className="flex justify-end p-6 border-t dark:border-gray-700">
              <button
                onClick={() => setShowCharModal(false)}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Importação */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
            <div className="p-6 border-b dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Importar Materiais e Itens</h2>
            </div>

            <div className="p-6">
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Selecione um arquivo CSV ou XLSX com as seguintes colunas (SEM cabeçalho):
              </p>
              <ul className="text-sm text-gray-500 dark:text-gray-400 mb-4 list-disc list-inside">
                <li><strong className="text-gray-700 dark:text-gray-300">Coluna 1:</strong> Código do material (9 dígitos numéricos)</li>
                <li><strong className="text-gray-700 dark:text-gray-300">Coluna 2:</strong> Nome do material</li>
                <li><strong className="text-gray-700 dark:text-gray-300">Coluna 3:</strong> Características no formato: CARACTERISTICA1: VALOR1, CARACTERISTICA2: VALOR2, ...</li>
              </ul>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Cliente (opcional)
                </label>
                <select
                  value={importClientId || ''}
                  onChange={(e) => setImportClientId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="">Sem cliente específico</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome_curto || c.nome}
                    </option>
                  ))}
                </select>
              </div>

              <input
                type="file"
                ref={fileInputRef}
                accept=".csv,.xlsx,.xls"
                onChange={handleImport}
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />

              {selectedFileName && uploading && (
                <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <p className="text-blue-700 dark:text-blue-300 font-medium flex items-center">
                    <svg className="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processando arquivo: {selectedFileName}
                  </p>
                </div>
              )}

              {importResult && !uploading && (
                <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-700 rounded-lg">
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    ✓ Criados: {importResult.created} | ↻ Atualizados: {importResult.updated} | ⊘ Ignorados: {importResult.skipped}
                  </p>
                  {importResult.errors && importResult.errors.length > 0 && (
                    <div className="mt-2 text-red-600 dark:text-red-400 text-sm">
                      <p className="font-medium">Erros:</p>
                      {importResult.errors.slice(0, 5).map((err, i) => (
                        <p key={i}>{err}</p>
                      ))}
                      {importResult.errors.length > 5 && (
                        <p>... e mais {importResult.errors.length - 5} erros</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 p-6 border-t dark:border-gray-700">
              <button
                onClick={() => {
                  setShowImportModal(false);
                  setImportResult(null);
                  setImportClientId(null);
                  setSelectedFileName(null);
                  setUploading(false);
                }}
                disabled={uploading}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </AdminRoute>
  )
}
