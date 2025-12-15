'use client'

import { useState, useCallback, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import Link from 'next/link'
import { quotesApi } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

interface Project {
  id: number
  nome: string
  client?: { nome: string; nome_curto?: string }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type SearchTab = 'descricao' | 'imagens'

export default function CotacaoPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const [inputText, setInputText] = useState('')
  const [codigo, setCodigo] = useState('')
  const [local, setLocal] = useState('')
  const [pesquisador, setPesquisador] = useState('')
  const [projectId, setProjectId] = useState<string>('')
  const [projects, setProjects] = useState<Project[]>([])
  const [images, setImages] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<SearchTab>('descricao')

  // Definir pesquisador como o nome do usuário autenticado
  useEffect(() => {
    if (user?.nome) {
      setPesquisador(user.nome)
    }
  }, [user])

  useEffect(() => {
    // Fetch projects for select
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

    // Check if project_id is in URL
    const urlProjectId = searchParams.get('project_id')
    if (urlProjectId) {
      setProjectId(urlProjectId)
    }
  }, [searchParams])

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setImages((prev) => [...prev, ...acceptedFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif']
    },
    multiple: true
  })

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!inputText && images.length === 0) {
      setError('Por favor, forneça uma descrição ou imagens')
      return
    }

    setLoading(true)

    try {
      const formData = new FormData()

      if (inputText) formData.append('inputText', inputText)
      if (codigo) formData.append('codigo', codigo)
      if (local) formData.append('local', local)
      if (pesquisador) formData.append('pesquisador', pesquisador)
      if (projectId) formData.append('project_id', projectId)

      images.forEach((image) => {
        formData.append('images', image)
      })

      const response = await quotesApi.create(formData)

      router.push(`/cotacao/${response.quoteRequestId}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar cotação')
      setLoading(false)
    }
  }

  const canSubmit = (inputText.trim() || images.length > 0) && !loading

  return (
    <div className="max-w-4xl">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Nova Cotação</h1>

        {/* Link para Google Lens */}
        <Link
          href="/cotacao/google-lens"
          className="flex items-center gap-2 px-4 py-2 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-lg hover:bg-indigo-200 dark:hover:bg-indigo-900/50 transition-colors"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          Identificar por Imagem
        </Link>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Projeto e Código do Item */}
        <div className="card">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Projeto (opcional)
              </label>
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="input-field w-full"
                disabled={loading}
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
                Código do Item (opcional)
              </label>
              <input
                type="text"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                className="input-field w-full"
                placeholder="Ex: 100002346"
                disabled={loading}
              />
            </div>
          </div>
        </div>

        {/* Local e Pesquisador */}
        <div className="card">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Local
              </label>
              <input
                type="text"
                value={local}
                onChange={(e) => setLocal(e.target.value)}
                className="input-field w-full"
                placeholder="Ex: Online"
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Pesquisador
              </label>
              <input
                type="text"
                value={pesquisador}
                readOnly
                className="input-field w-full bg-gray-100 dark:bg-gray-700 cursor-not-allowed"
                placeholder="Ex: João Silva"
              />
            </div>
          </div>
        </div>

        {/* Pesquisa por: Abas */}
        <div className="card">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
            Pesquisar por:
          </label>

          {/* Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-700 mb-4">
            <nav className="-mb-px flex space-x-8">
              <button
                type="button"
                onClick={() => setActiveTab('descricao')}
                className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'descricao'
                    ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                Descrição
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('imagens')}
                className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'imagens'
                    ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                Imagens (Etiqueta ou Foto do Bem)
              </button>
            </nav>
          </div>

          {/* Tab Content: Descrição */}
          {activeTab === 'descricao' && (
            <div>
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="input-field w-full min-h-[150px]"
                placeholder="Digite a descrição do item ou equipamento..."
                disabled={loading}
              />
            </div>
          )}

          {/* Tab Content: Imagens */}
          {activeTab === 'imagens' && (
            <div>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragActive
                    ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                    : 'border-gray-300 dark:border-gray-600 hover:border-primary-400'
                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input {...getInputProps()} disabled={loading} />
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 48 48"
                >
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  {isDragActive
                    ? 'Solte as imagens aqui...'
                    : 'Arraste imagens ou clique para selecionar'}
                </p>
              </div>

              {images.length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-4">
                  {images.map((image, index) => (
                    <div key={index} className="relative">
                      <img
                        src={URL.createObjectURL(image)}
                        alt={`Preview ${index + 1}`}
                        className="w-full h-40 object-cover rounded-lg"
                      />
                      <button
                        type="button"
                        onClick={() => removeImage(index)}
                        className="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                        disabled={loading}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                      <p className="mt-1 text-xs text-gray-600 dark:text-gray-400 truncate">{image.name}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Submit buttons */}
        <div className="flex justify-end space-x-4">
          <button
            type="button"
            onClick={() => router.push('/historico')}
            className="btn-secondary"
            disabled={loading}
          >
            Cancelar
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={!canSubmit}
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Processando...
              </span>
            ) : (
              'Iniciar Cotação'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
