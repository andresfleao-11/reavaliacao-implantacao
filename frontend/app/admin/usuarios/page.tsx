'use client'

import { useState, useEffect } from 'react'
import AdminRoute from '@/components/AdminRoute'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Helper para obter headers com autenticação
const getAuthHeaders = () => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  }
}

interface User {
  id: number
  email: string
  nome: string
  role: string
  ativo: boolean
  created_at: string
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [formData, setFormData] = useState({
    nome: '',
    email: '',
    password: '',
    role: 'USER',
    ativo: true
  })
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ new_password: '' })
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/users`, {
        headers: getAuthHeaders()
      })
      const data = await res.json()
      // Garantir que users seja sempre um array, mesmo se a API retornar erro
      setUsers(data.items || [])
      if (!res.ok) {
        setError(data.detail || 'Erro ao carregar usuários')
      }
    } catch (err) {
      console.error('Erro ao carregar usuários:', err)
      setUsers([])
      setError('Erro de conexão com o servidor')
    } finally {
      setLoading(false)
    }
  }

  const openNewModal = () => {
    setEditingUser(null)
    setFormData({
      nome: '',
      email: '',
      password: '',
      role: 'USER',
      ativo: true
    })
    setError('')
    setShowModal(true)
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setFormData({
      nome: user.nome,
      email: user.email,
      password: '',
      role: user.role,
      ativo: user.ativo
    })
    setError('')
    setShowModal(true)
  }

  const openPasswordModal = (userId: number) => {
    setSelectedUserId(userId)
    setPasswordForm({ new_password: '' })
    setShowPasswordModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    try {
      const url = editingUser
        ? `${API_URL}/api/users/${editingUser.id}`
        : `${API_URL}/api/users`

      const method = editingUser ? 'PUT' : 'POST'

      const payload: any = {
        nome: formData.nome,
        email: formData.email,
        role: formData.role,
        ativo: formData.ativo
      }

      if (!editingUser) {
        payload.password = formData.password
      }

      const res = await fetch(url, {
        method,
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao salvar')
      }

      await fetchUsers()
      setShowModal(false)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handlePasswordReset = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!selectedUserId) return

    try {
      const res = await fetch(`${API_URL}/api/users/${selectedUserId}/reset-password`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ new_password: passwordForm.new_password })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao resetar senha')
      }

      alert('Senha alterada com sucesso')
      setShowPasswordModal(false)
    } catch (err: any) {
      alert(err.message)
    }
  }

  const handleDelete = async (userId: number) => {
    if (!confirm('Tem certeza que deseja excluir este usuário?')) return

    try {
      const res = await fetch(`${API_URL}/api/users/${userId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao excluir')
      }

      await fetchUsers()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const toggleStatus = async (user: User) => {
    try {
      const res = await fetch(`${API_URL}/api/users/${user.id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ ativo: !user.ativo })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao alterar status')
      }

      await fetchUsers()
    } catch (err: any) {
      alert(err.message)
    }
  }

  if (loading) {
    return (
      <div className="max-w-6xl">
        <h1 className="text-3xl font-bold mb-8 text-gray-900 dark:text-gray-100">
          Gerenciamento de Usuários
        </h1>
        <p className="text-gray-600 dark:text-gray-400">Carregando...</p>
      </div>
    )
  }

  return (
    <AdminRoute>
    <div className="max-w-6xl">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
          Gerenciamento de Usuários
        </h1>
        <button
          onClick={openNewModal}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          Novo Usuário
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Nome
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Email
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Perfil
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Ações
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {(users || []).map((user) => (
              <tr key={user.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-gray-100">
                  {user.nome}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {user.email}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      user.role === 'ADMIN'
                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                        : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                    }`}
                  >
                    {user.role === 'ADMIN' ? 'Administrador' : 'Usuário'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    onClick={() => toggleStatus(user)}
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      user.ativo
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    }`}
                  >
                    {user.ativo ? 'Ativo' : 'Bloqueado'}
                  </button>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                  <button
                    onClick={() => openEditModal(user)}
                    className="text-primary-600 dark:text-primary-400 hover:text-primary-900 dark:hover:text-primary-300"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => openPasswordModal(user.id)}
                    className="text-yellow-600 dark:text-yellow-400 hover:text-yellow-900 dark:hover:text-yellow-300"
                  >
                    Resetar Senha
                  </button>
                  <button
                    onClick={() => handleDelete(user.id)}
                    className="text-red-600 dark:text-red-400 hover:text-red-900 dark:hover:text-red-300"
                  >
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal de Criar/Editar */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-gray-100">
                {editingUser ? 'Editar Usuário' : 'Novo Usuário'}
              </h2>

              {error && (
                <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit}>
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
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Email *
                    </label>
                    <input
                      type="email"
                      required
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>

                  {!editingUser && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Senha *
                      </label>
                      <input
                        type="password"
                        required
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Perfil *
                    </label>
                    <select
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    >
                      <option value="USER">Usuário</option>
                      <option value="ADMIN">Administrador</option>
                    </select>
                  </div>

                  {editingUser && (
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="ativo"
                        checked={formData.ativo}
                        onChange={(e) => setFormData({ ...formData, ativo: e.target.checked })}
                        className="w-4 h-4 text-primary-600 rounded"
                      />
                      <label htmlFor="ativo" className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Usuário ativo
                      </label>
                    </div>
                  )}
                </div>

                <div className="flex justify-end gap-3 mt-6 pt-4 border-t dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                  >
                    {editingUser ? 'Salvar' : 'Criar'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Resetar Senha */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full">
            <div className="p-6">
              <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-gray-100">
                Resetar Senha
              </h2>

              <form onSubmit={handlePasswordReset}>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Nova Senha *
                  </label>
                  <input
                    type="password"
                    required
                    value={passwordForm.new_password}
                    onChange={(e) => setPasswordForm({ new_password: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => setShowPasswordModal(false)}
                    className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                  >
                    Resetar Senha
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
    </AdminRoute>
  )
}
