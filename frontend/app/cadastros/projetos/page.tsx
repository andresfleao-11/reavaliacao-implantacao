'use client'

import { useState, useEffect } from 'react'
import AdminRoute from '@/components/AdminRoute'

interface Client {
  id: number
  nome: string
  nome_curto: string | null
}

interface Project {
  id: number
  client_id: number
  client: Client | null
  nome: string
  codigo: string | null
  descricao: string | null
  numero_contrato: string | null
  numero_processo: string | null
  modalidade_licitacao: string | null
  data_inicio: string | null
  data_previsao_fim: string | null
  data_fim: string | null
  valor_contrato: number | null
  status: string
  responsavel_tecnico: string | null
  responsavel_cliente: string | null
  observacoes: string | null
  created_at: string
  total_cotacoes: number
}

interface ProjectListResponse {
  items: Project[]
  total: number
  page: number
  per_page: number
}

interface StatusOption {
  value: string
  label: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const emptyProject = {
  client_id: 0,
  nome: '',
  codigo: '',
  descricao: '',
  numero_contrato: '',
  numero_processo: '',
  modalidade_licitacao: '',
  data_inicio: '',
  data_previsao_fim: '',
  valor_contrato: '',
  status: 'PLANEJAMENTO',
  responsavel_tecnico: '',
  responsavel_cliente: '',
  observacoes: '',
}

const modalidades = [
  'Pregão Eletrônico',
  'Pregão Presencial',
  'Concorrência',
  'Tomada de Preços',
  'Convite',
  'Dispensa de Licitação',
  'Inexigibilidade',
  'Adesão a Ata',
]

export default function ProjetosPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [statusOptions, setStatusOptions] = useState<StatusOption[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterClientId, setFilterClientId] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [showModal, setShowModal] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [formData, setFormData] = useState(emptyProject)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const perPage = 10

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
      })
      if (search) params.append('search', search)
      if (filterClientId) params.append('client_id', filterClientId)
      if (filterStatus) params.append('status', filterStatus)

      const res = await fetch(`${API_URL}/api/projects?${params}`)
      const data: ProjectListResponse = await res.json()
      setProjects(data.items)
      setTotal(data.total)
    } catch (err) {
      console.error('Erro ao carregar projetos:', err)
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

  const fetchStatusOptions = async () => {
    try {
      const res = await fetch(`${API_URL}/api/projects/status/options`)
      const data = await res.json()
      setStatusOptions(data)
    } catch (err) {
      console.error('Erro ao carregar status:', err)
    }
  }

  useEffect(() => {
    fetchClients()
    fetchStatusOptions()
  }, [])

  useEffect(() => {
    fetchProjects()
  }, [page, search, filterClientId, filterStatus])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchProjects()
  }

  const openNewModal = () => {
    setEditingProject(null)
    setFormData(emptyProject)
    setError('')
    setShowModal(true)
  }

  const openEditModal = (project: Project) => {
    setEditingProject(project)
    setFormData({
      client_id: project.client_id,
      nome: project.nome,
      codigo: project.codigo || '',
      descricao: project.descricao || '',
      numero_contrato: project.numero_contrato || '',
      numero_processo: project.numero_processo || '',
      modalidade_licitacao: project.modalidade_licitacao || '',
      data_inicio: project.data_inicio ? project.data_inicio.split('T')[0] : '',
      data_previsao_fim: project.data_previsao_fim ? project.data_previsao_fim.split('T')[0] : '',
      valor_contrato: project.valor_contrato?.toString() || '',
      status: project.status,
      responsavel_tecnico: project.responsavel_tecnico || '',
      responsavel_cliente: project.responsavel_cliente || '',
      observacoes: project.observacoes || '',
    })
    setError('')
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')

    try {
      const url = editingProject
        ? `${API_URL}/api/projects/${editingProject.id}`
        : `${API_URL}/api/projects`
      const method = editingProject ? 'PUT' : 'POST'

      const payload: any = {
        ...formData,
        client_id: Number(formData.client_id),
        valor_contrato: formData.valor_contrato ? Number(formData.valor_contrato) : null,
        data_inicio: formData.data_inicio || null,
        data_previsao_fim: formData.data_previsao_fim || null,
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
      fetchProjects()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (project: Project) => {
    if (!confirm(`Deseja realmente excluir o projeto "${project.nome}"?`)) return

    try {
      const res = await fetch(`${API_URL}/api/projects/${project.id}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao excluir')
      }

      fetchProjects()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      PLANEJAMENTO: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200',
      EM_ANDAMENTO: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300',
      CONCLUIDO: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300',
      CANCELADO: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
      SUSPENSO: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300',
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
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Projetos</h1>
        <button
          onClick={openNewModal}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          Novo Projeto
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 mb-6">
        <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome ou código..."
            className="flex-1 min-w-[200px] px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
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
            {statusOptions.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <button
            type="submit"
            className="px-6 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Buscar
          </button>
        </form>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Carregando...</div>
        ) : projects.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            Nenhum projeto encontrado
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Projeto
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Cliente
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Contrato
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Cotações
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {projects.map((project) => (
                  <tr key={project.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{project.nome}</div>
                      {project.codigo && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">Cód: {project.codigo}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                      {project.client?.nome_curto || project.client?.nome || '-'}
                    </td>
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                      {project.numero_contrato || '-'}
                      {project.modalidade_licitacao && (
                        <div className="text-xs text-gray-400 dark:text-gray-500">{project.modalidade_licitacao}</div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {getStatusBadge(project.status)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300">
                        {project.total_cotacoes}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <a
                        href={`/cadastros/projetos/${project.id}`}
                        className="text-green-600 dark:text-green-400 hover:text-green-800 dark:hover:text-green-300 mr-3"
                      >
                        Detalhes
                      </a>
                      <button
                        onClick={() => openEditModal(project)}
                        className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 mr-3"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(project)}
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
              <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Mostrando {(page - 1) * perPage + 1} a {Math.min(page * perPage, total)} de {total} resultados
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
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
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {editingProject ? 'Editar Projeto' : 'Novo Projeto'}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="p-6">
              {error && (
                <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Cliente *
                  </label>
                  <select
                    required
                    value={formData.client_id}
                    onChange={(e) => setFormData({ ...formData, client_id: Number(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">Selecione o cliente...</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>{c.nome}</option>
                    ))}
                  </select>
                </div>

                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Nome do Projeto *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.nome}
                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Código
                  </label>
                  <input
                    type="text"
                    value={formData.codigo}
                    onChange={(e) => setFormData({ ...formData, codigo: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Status
                  </label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    {statusOptions.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Número do Contrato
                  </label>
                  <input
                    type="text"
                    value={formData.numero_contrato}
                    onChange={(e) => setFormData({ ...formData, numero_contrato: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Número do Processo
                  </label>
                  <input
                    type="text"
                    value={formData.numero_processo}
                    onChange={(e) => setFormData({ ...formData, numero_processo: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Modalidade de Licitação
                  </label>
                  <select
                    value={formData.modalidade_licitacao}
                    onChange={(e) => setFormData({ ...formData, modalidade_licitacao: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">Selecione...</option>
                    {modalidades.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Valor do Contrato (R$)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.valor_contrato}
                    onChange={(e) => setFormData({ ...formData, valor_contrato: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Data de Início
                  </label>
                  <input
                    type="date"
                    value={formData.data_inicio}
                    onChange={(e) => setFormData({ ...formData, data_inicio: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Previsão de Término
                  </label>
                  <input
                    type="date"
                    value={formData.data_previsao_fim}
                    onChange={(e) => setFormData({ ...formData, data_previsao_fim: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Responsável Técnico
                  </label>
                  <input
                    type="text"
                    value={formData.responsavel_tecnico}
                    onChange={(e) => setFormData({ ...formData, responsavel_tecnico: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Responsável Cliente
                  </label>
                  <input
                    type="text"
                    value={formData.responsavel_cliente}
                    onChange={(e) => setFormData({ ...formData, responsavel_cliente: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div className="col-span-2">
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

                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Observações
                  </label>
                  <textarea
                    value={formData.observacoes}
                    onChange={(e) => setFormData({ ...formData, observacoes: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
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
