'use client'

import { useState, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { batchQuotesApi, api } from '@/lib/api'

type InputMethod = 'text' | 'images' | 'file'

interface Project {
  id: number
  nome: string
  cliente_nome: string | null
}

export default function BatchQuotePage() {
  const router = useRouter()
  const [inputMethod, setInputMethod] = useState<InputMethod>('text')
  const [textInput, setTextInput] = useState('')
  const [images, setImages] = useState<File[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [projectId, setProjectId] = useState<string>('')
  const [local, setLocal] = useState('')
  const [pesquisador, setPesquisador] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [itemCount, setItemCount] = useState(0)

  // Carregar usuario atual e projetos
  useEffect(() => {
    const loadData = async () => {
      try {
        // Carregar usuario para pesquisador
        const userStr = localStorage.getItem('user')
        if (userStr) {
          const user = JSON.parse(userStr)
          setPesquisador(user.name || user.email || '')
        }

        // Carregar projetos
        const response = await api.get('/api/projects')
        setProjects(response.data.items || [])
      } catch (err) {
        console.error('Error loading data:', err)
      }
    }
    loadData()
  }, [])

  // Contar itens baseado no metodo de entrada
  useEffect(() => {
    if (inputMethod === 'text') {
      const items = textInput.split(';').filter(item => item.trim().length >= 3)
      setItemCount(items.length)
    } else if (inputMethod === 'images') {
      setItemCount(images.length)
    } else if (inputMethod === 'file' && file) {
      // Para arquivo, nao sabemos o count ate fazer o parse no backend
      setItemCount(-1) // -1 indica "sera calculado"
    } else {
      setItemCount(0)
    }
  }, [inputMethod, textInput, images, file])

  // Dropzone para imagens
  const onDropImages = useCallback((acceptedFiles: File[]) => {
    const newImages = acceptedFiles.filter(
      file => file.type.startsWith('image/')
    )
    setImages(prev => [...prev, ...newImages])
    setError('')
  }, [])

  const { getRootProps: getImagesRootProps, getInputProps: getImagesInputProps, isDragActive: isImagesDragActive } = useDropzone({
    onDrop: onDropImages,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp']
    },
    multiple: true,
    maxSize: 5 * 1024 * 1024, // 5MB per file
  })

  // Dropzone para arquivo CSV/XLSX
  const onDropFile = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const f = acceptedFiles[0]
      const ext = f.name.split('.').pop()?.toLowerCase()
      if (ext === 'csv' || ext === 'xlsx' || ext === 'xls') {
        setFile(f)
        setError('')
      } else {
        setError('Formato inválido. Use CSV ou XLSX.')
      }
    }
  }, [])

  const { getRootProps: getFileRootProps, getInputProps: getFileInputProps, isDragActive: isFileDragActive } = useDropzone({
    onDrop: onDropFile,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    multiple: false,
    maxSize: 10 * 1024 * 1024, // 10MB
  })

  const removeImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    setError('')
    setLoading(true)

    try {
      let result

      if (inputMethod === 'text') {
        if (!textInput.trim()) {
          throw new Error('Digite as descrições dos produtos separadas por ";"')
        }
        result = await batchQuotesApi.createTextBatch({
          input_text: textInput,
          local: local || undefined,
          pesquisador: pesquisador || undefined,
          project_id: projectId ? parseInt(projectId) : undefined,
        })
      } else if (inputMethod === 'images') {
        if (images.length === 0) {
          throw new Error('Selecione ao menos uma imagem')
        }
        result = await batchQuotesApi.createImageBatch({
          images,
          local: local || undefined,
          pesquisador: pesquisador || undefined,
          project_id: projectId ? parseInt(projectId) : undefined,
        })
      } else if (inputMethod === 'file') {
        if (!file) {
          throw new Error('Selecione um arquivo CSV ou XLSX')
        }
        result = await batchQuotesApi.createFileBatch({
          file,
          local: local || undefined,
          pesquisador: pesquisador || undefined,
          project_id: projectId ? parseInt(projectId) : undefined,
        })
      }

      // Redirecionar para pagina de detalhe do lote
      router.push(`/cotacao/lote/${result.batch_id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Erro ao criar lote')
    } finally {
      setLoading(false)
    }
  }

  const canSubmit = () => {
    if (loading) return false
    if (inputMethod === 'text') return textInput.trim().length > 0
    if (inputMethod === 'images') return images.length > 0
    if (inputMethod === 'file') return file !== null
    return false
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Cotação em Lote
        </h1>

        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Configurações do Lote */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Configurações
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Projeto (opcional)
              </label>
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Sem projeto</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome} {p.cliente_nome ? `(${p.cliente_nome})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Local (opcional)
              </label>
              <input
                type="text"
                value={local}
                onChange={(e) => setLocal(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                placeholder="Ex: Sao Paulo"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Pesquisador
              </label>
              <input
                type="text"
                value={pesquisador}
                onChange={(e) => setPesquisador(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                placeholder="Nome do pesquisador"
              />
            </div>
          </div>
        </div>

        {/* Metodo de Entrada */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Metodo de Entrada
          </h2>

          {/* Tabs */}
          <div className="flex border-b border-gray-200 dark:border-gray-700 mb-4">
            <button
              onClick={() => setInputMethod('text')}
              className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
                inputMethod === 'text'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              Texto
            </button>
            <button
              onClick={() => setInputMethod('images')}
              className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
                inputMethod === 'images'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              Imagens
            </button>
            <button
              onClick={() => setInputMethod('file')}
              className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
                inputMethod === 'file'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              Arquivo
            </button>
          </div>

          {/* Tab Content */}
          {inputMethod === 'text' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Descricoes dos produtos (separadas por &quot;;&quot;)
              </label>
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 min-h-[150px]"
                placeholder="Notebook Dell 15 i7 16GB; Mouse Logitech MX Master 3; Teclado Mecanico RGB"
              />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Separe cada produto com ponto-e-virgula (;)
              </p>
            </div>
          )}

          {inputMethod === 'images' && (
            <div>
              {/* Desktop: Dropzone */}
              <div className="hidden sm:block">
                <div
                  {...getImagesRootProps()}
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    isImagesDragActive
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                  }`}
                >
                  <input {...getImagesInputProps()} accept="image/*" />
                  <div className="text-gray-500 dark:text-gray-400">
                    <svg className="mx-auto h-12 w-12 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="font-medium">Arraste imagens aqui ou clique para selecionar</p>
                    <p className="text-sm mt-1">Multiplas imagens permitidas - uma por produto (PNG, JPG, WEBP)</p>
                  </div>
                </div>
              </div>

              {/* Mobile: Botões separados para Câmera e Galeria */}
              <div className="sm:hidden space-y-3">
                <p className="text-sm text-gray-600 dark:text-gray-400 text-center mb-4">
                  Multiplas imagens permitidas - uma por produto
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {/* Botão Câmera */}
                  <label className="flex flex-col items-center justify-center p-4 border-2 border-dashed rounded-lg cursor-pointer transition-colors border-blue-400 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30">
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        const files = Array.from(e.target.files || [])
                        if (files.length > 0) setImages(prev => [...prev, ...files])
                        e.target.value = ''
                      }}
                    />
                    <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span className="mt-2 text-sm font-medium text-blue-600 dark:text-blue-400">Tirar Foto</span>
                  </label>

                  {/* Botão Galeria */}
                  <label className="flex flex-col items-center justify-center p-4 border-2 border-dashed rounded-lg cursor-pointer transition-colors border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800">
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        const files = Array.from(e.target.files || [])
                        if (files.length > 0) setImages(prev => [...prev, ...files])
                        e.target.value = ''
                      }}
                    />
                    <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span className="mt-2 text-sm font-medium text-gray-600 dark:text-gray-400">Galeria</span>
                  </label>
                </div>
                {images.length > 0 && (
                  <p className="text-xs text-center text-gray-500">{images.length} imagem(ns) selecionada(s)</p>
                )}
              </div>

              {images.length > 0 && (
                <div className="mt-4 grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
                  {images.map((img, idx) => (
                    <div key={idx} className="relative group">
                      <img
                        src={URL.createObjectURL(img)}
                        alt={`Imagem ${idx + 1}`}
                        className="w-full h-16 object-cover rounded border border-gray-200 dark:border-gray-700"
                      />
                      <button
                        onClick={() => removeImage(idx)}
                        className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        x
                      </button>
                      <span className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs text-center">
                        {idx + 1}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {inputMethod === 'file' && (
            <div>
              <div
                {...getFileRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isFileDragActive
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                }`}
              >
                <input {...getFileInputProps()} />
                <div className="text-gray-500 dark:text-gray-400">
                  <svg className="mx-auto h-12 w-12 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="font-medium">Arraste um arquivo CSV ou XLSX aqui</p>
                  <p className="text-sm mt-1">A primeira coluna deve conter as descrições dos produtos</p>
                </div>
              </div>

              {file && (
                <div className="mt-4 flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                  <div className="flex items-center gap-3">
                    <svg className="h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">{file.name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {(file.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setFile(null)}
                    className="text-red-500 hover:text-red-700"
                  >
                    Remover
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Contador e Botao */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div className="text-gray-700 dark:text-gray-300">
              {itemCount > 0 && (
                <span className="text-lg font-medium">
                  {itemCount} {itemCount === 1 ? 'item' : 'itens'} identificados
                </span>
              )}
              {itemCount === -1 && (
                <span className="text-sm text-gray-500">
                  Quantidade sera calculada apos o upload
                </span>
              )}
              {itemCount === 0 && inputMethod !== 'file' && (
                <span className="text-sm text-gray-500">
                  Nenhum item identificado
                </span>
              )}
            </div>
            <button
              onClick={handleSubmit}
              disabled={!canSubmit()}
              className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                canSubmit()
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              }`}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Criando lote...
                </span>
              ) : (
                'Iniciar Cotação em Lote'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
