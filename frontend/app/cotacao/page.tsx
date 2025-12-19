'use client'

import { useState, useCallback, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import Link from 'next/link'
import { quotesApi, API_URL } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import BarcodeScanner from '@/components/BarcodeScanner'

interface Project {
  id: number
  nome: string
  client?: { nome: string; nome_curto?: string }
}

type SearchTab = 'descricao' | 'imagens'

function CotacaoContent() {
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
  const [scannerOpen, setScannerOpen] = useState(false)

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
    // Cotação individual: aceita apenas 1 imagem
    if (acceptedFiles.length > 0) {
      setImages([acceptedFiles[0]])
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif']
    },
    multiple: false,  // Cotação individual: apenas 1 imagem
    maxFiles: 1
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
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 sm:mb-8">
        <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-gray-900 dark:text-gray-100">Nova Cotação</h1>

        {/* Link para Google Lens */}
        <Link
          href="/cotacao/google-lens"
          className="flex items-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-lg hover:bg-indigo-200 dark:hover:bg-indigo-900/50 transition-colors"
        >
          <svg className="w-4 h-4 sm:w-5 sm:h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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

      <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
        {/* Projeto e Código do Item */}
        <div className="card">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 sm:mb-2">
                Projeto (opcional)
              </label>
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="input-field w-full text-sm"
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
              <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 sm:mb-2">
                Código do Item (opcional)
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value)}
                  className="input-field w-full text-sm pr-10 sm:pr-3"
                  placeholder="Ex: 100002346"
                  disabled={loading}
                />
                {/* Ícone de scanner de código de barras - apenas mobile */}
                <button
                  type="button"
                  onClick={() => setScannerOpen(true)}
                  className="sm:hidden absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-500 hover:text-primary-500 transition-colors"
                  disabled={loading}
                  title="Escanear código de barras"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12h2m2 0h.01M4 4h4M4 8h4m4 12h2M4 16h4m12-4h.01M12 20h.01" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Local e Pesquisador */}
        <div className="card">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 sm:mb-2">
                Local
              </label>
              <input
                type="text"
                value={local}
                onChange={(e) => setLocal(e.target.value)}
                className="input-field w-full text-sm"
                placeholder="Ex: Online"
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 sm:mb-2">
                Pesquisador
              </label>
              <input
                type="text"
                value={pesquisador}
                readOnly
                className="input-field w-full text-sm bg-gray-100 dark:bg-gray-700 cursor-not-allowed"
                placeholder="Ex: João Silva"
              />
            </div>
          </div>
        </div>

        {/* Pesquisa por: Abas */}
        <div className="card">
          <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 sm:mb-4">
            Pesquisar por:
          </label>

          {/* Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-700 mb-4">
            <nav className="-mb-px flex space-x-4 sm:space-x-8">
              <button
                type="button"
                onClick={() => setActiveTab('descricao')}
                className={`py-2 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors ${
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
                className={`py-2 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors ${
                  activeTab === 'imagens'
                    ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                Imagens
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
              {/* Desktop: Dropzone */}
              <div className="hidden sm:block">
                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    isDragActive
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:border-primary-400'
                  } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <input {...getInputProps()} disabled={loading} accept="image/*" />
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
                      ? 'Solte a imagem aqui...'
                      : 'Arraste uma imagem ou clique para selecionar'}
                  </p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
                    Apenas 1 imagem permitida
                  </p>
                </div>
              </div>

              {/* Mobile: Botões separados para Câmera e Galeria */}
              <div className="sm:hidden space-y-3">
                <p className="text-sm text-gray-600 dark:text-gray-400 text-center mb-4">
                  Apenas 1 imagem permitida
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {/* Botão Câmera */}
                  <label className={`flex flex-col items-center justify-center p-4 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                    loading ? 'opacity-50 cursor-not-allowed' : 'border-primary-400 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30'
                  }`}>
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="hidden"
                      disabled={loading}
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) setImages([file])
                        e.target.value = ''
                      }}
                    />
                    <svg className="w-8 h-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span className="mt-2 text-sm font-medium text-primary-600 dark:text-primary-400">Tirar Foto</span>
                  </label>

                  {/* Botão Galeria */}
                  <label className={`flex flex-col items-center justify-center p-4 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                    loading ? 'opacity-50 cursor-not-allowed' : 'border-gray-300 dark:border-gray-600 hover:border-primary-400 hover:bg-gray-50 dark:hover:bg-gray-800'
                  }`}>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      disabled={loading}
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) setImages([file])
                        e.target.value = ''
                      }}
                    />
                    <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span className="mt-2 text-sm font-medium text-gray-600 dark:text-gray-400">Galeria</span>
                  </label>
                </div>
              </div>

              {images.length > 0 && (
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-4">
                  {images.map((image, index) => (
                    <div key={index} className="relative">
                      <img
                        src={URL.createObjectURL(image)}
                        alt={`Preview ${index + 1}`}
                        className="w-full h-24 sm:h-40 object-cover rounded-lg"
                      />
                      <button
                        type="button"
                        onClick={() => removeImage(index)}
                        className="absolute top-1 right-1 sm:top-2 sm:right-2 bg-red-500 text-white rounded-full p-0.5 sm:p-1 hover:bg-red-600"
                        disabled={loading}
                      >
                        <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
        <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 sm:space-x-4">
          <button
            type="button"
            onClick={() => router.push('/historico')}
            className="btn-secondary text-sm"
            disabled={loading}
          >
            Cancelar
          </button>
          <button
            type="submit"
            className="btn-primary text-sm"
            disabled={!canSubmit}
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24">
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

      {/* Scanner de código de barras */}
      <BarcodeScanner
        isOpen={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={(code) => setCodigo(code)}
      />
    </div>
  )
}

export default function CotacaoPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div></div>}>
      <CotacaoContent />
    </Suspense>
  )
}
