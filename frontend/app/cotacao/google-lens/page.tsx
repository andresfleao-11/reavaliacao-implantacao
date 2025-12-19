'use client'

import { useState, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import Link from 'next/link'
import { lensApi, LensProduct, LensSpecs, API_URL } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

interface Project {
  id: number
  nome: string
  client?: { nome: string; nome_curto?: string }
}

type LensStep = 'upload' | 'select' | 'confirm'

export default function GoogleLensPage() {
  const router = useRouter()
  const { user } = useAuth()

  // Form fields
  const [codigo, setCodigo] = useState('')
  const [local, setLocal] = useState('')
  const [pesquisador, setPesquisador] = useState('')
  const [projectId, setProjectId] = useState<string>('')
  const [projects, setProjects] = useState<Project[]>([])

  // Lens state
  const [lensImage, setLensImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [lensLoading, setLensLoading] = useState(false)
  const [lensProducts, setLensProducts] = useState<LensProduct[]>([])
  const [lensApiCalls, setLensApiCalls] = useState<any[]>([])
  const [selectedProduct, setSelectedProduct] = useState<LensProduct | null>(null)
  const [extractedSpecs, setExtractedSpecs] = useState<LensSpecs | null>(null)
  const [specsLoading, setSpecsLoading] = useState(false)
  const [lensStep, setLensStep] = useState<LensStep>('upload')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Set default pesquisador
  useEffect(() => {
    if (user?.nome) {
      setPesquisador(user.nome)
    }
  }, [user])

  // Load projects
  useEffect(() => {
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
  }, [])

  // Dropzone for image
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0]
      setLensImage(file)
      setImagePreview(URL.createObjectURL(file))
      setLensProducts([])
      setSelectedProduct(null)
      setExtractedSpecs(null)
      setLensStep('upload')
      setError('')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg', '.webp'] },
    maxFiles: 1,
    multiple: false
  })

  // Search with Google Lens
  const handleSearch = async () => {
    if (!lensImage) return

    setLensLoading(true)
    setError('')

    try {
      const result = await lensApi.search(lensImage)
      setLensProducts(result.products)
      setLensApiCalls(result.api_calls || [])
      setLensStep('select')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao buscar com Google Lens')
    } finally {
      setLensLoading(false)
    }
  }

  // Select product and extract specs
  const handleSelectProduct = async (product: LensProduct) => {
    setSelectedProduct(product)
    setSpecsLoading(true)
    setError('')

    try {
      const result = await lensApi.extractSpecs(product.link)
      setExtractedSpecs(result.specs)
      setLensStep('confirm')
    } catch (err: any) {
      // If extraction fails, use basic info
      setExtractedSpecs({
        nome: product.title,
        marca: null,
        modelo: null,
        tipo_produto: null,
        especificacoes: {},
        preco: product.extracted_price,
        url_fonte: product.link
      })
      setLensStep('confirm')
    } finally {
      setSpecsLoading(false)
    }
  }

  // Create quote
  const handleCreateQuote = async () => {
    if (!selectedProduct || !extractedSpecs) return

    setLoading(true)
    setError('')

    try {
      const response = await lensApi.createQuote({
        product_url: selectedProduct.link,
        product_title: extractedSpecs.nome || selectedProduct.title,
        marca: extractedSpecs.marca || undefined,
        modelo: extractedSpecs.modelo || undefined,
        tipo_produto: extractedSpecs.tipo_produto || undefined,
        especificacoes: extractedSpecs.especificacoes,
        codigo: codigo || undefined,
        local: local || undefined,
        pesquisador: pesquisador || undefined,
        project_id: projectId ? parseInt(projectId) : undefined,
        image: lensImage || undefined,
        lens_api_calls: lensApiCalls
      })

      router.push(`/cotacao/${response.quoteRequestId}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar cotação')
      setLoading(false)
    }
  }

  // Choose another product
  const handleChooseAnother = () => {
    setSelectedProduct(null)
    setExtractedSpecs(null)
    setLensStep('select')
  }

  // Reset everything
  const handleReset = () => {
    setLensImage(null)
    setImagePreview(null)
    setLensProducts([])
    setLensApiCalls([])
    setSelectedProduct(null)
    setExtractedSpecs(null)
    setLensStep('upload')
    setError('')
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6 sm:mb-8">
        <div className="flex items-center space-x-3 sm:space-x-4">
          <Link
            href="/cotacao"
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </Link>
          <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-gray-900 dark:text-gray-100">
            Identificação de Bem
          </h1>
        </div>
        <span className="self-start sm:self-auto px-3 py-1 rounded-full text-xs sm:text-sm font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
          🔍 Google Lens
        </span>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {/* Step 1: Upload Image */}
      {lensStep === 'upload' && (
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6">
            Etapa 1: Envie uma imagem do produto
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Dropzone */}
            <div>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  isDragActive
                    ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                    : 'border-gray-300 dark:border-gray-600 hover:border-primary-400 hover:bg-gray-50 dark:hover:bg-gray-800'
                }`}
              >
                <input {...getInputProps()} capture="environment" />
                <div className="space-y-4">
                  <div className="w-16 h-16 mx-auto bg-indigo-100 dark:bg-indigo-900/30 rounded-full flex items-center justify-center">
                    <svg className="w-8 h-8 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-lg font-medium text-gray-900 dark:text-gray-100">
                      {isDragActive ? 'Solte a imagem aqui' : 'Arraste uma imagem ou clique para selecionar'}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      PNG, JPG ou WEBP
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                      No celular, voce pode usar a camera para tirar fotos
                    </p>
                  </div>
                </div>
              </div>

              {/* Image Preview */}
              {imagePreview && (
                <div className="mt-6">
                  <div className="relative rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
                    <img
                      src={imagePreview}
                      alt="Preview"
                      className="w-full h-64 object-contain bg-gray-100 dark:bg-gray-800"
                    />
                    <button
                      onClick={handleReset}
                      className="absolute top-2 right-2 p-2 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Form fields */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Projeto (opcional)
                </label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="input-field w-full"
                >
                  <option value="">Sem projeto vinculado</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nome} {p.client ? `(${p.client.nome_curto || p.client.nome})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Código (Material)
                </label>
                <input
                  type="text"
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value)}
                  className="input-field w-full"
                  placeholder="Ex: ITEM-001"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Local
                </label>
                <input
                  type="text"
                  value={local}
                  onChange={(e) => setLocal(e.target.value)}
                  className="input-field w-full"
                  placeholder="Ex: São Paulo, SP"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Pesquisador
                </label>
                <input
                  type="text"
                  value={pesquisador}
                  onChange={(e) => setPesquisador(e.target.value)}
                  className="input-field w-full"
                  placeholder="Nome do pesquisador"
                />
              </div>

              <div className="pt-4">
                <button
                  onClick={handleSearch}
                  disabled={!lensImage || lensLoading}
                  className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {lensLoading ? 'Identificando...' : 'Identificar Produto'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Select Product */}
      {lensStep === 'select' && (
        <div className="card">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              Etapa 2: Selecione o Bem para cotação
            </h2>
            <button
              onClick={handleReset}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 flex items-center"
            >
              <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Nova busca
            </button>
          </div>

          {lensProducts.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-gray-500 dark:text-gray-400 text-lg">Nenhum produto encontrado.</p>
              <button
                onClick={handleReset}
                className="mt-4 text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium"
              >
                Tentar com outra imagem
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-gray-600 dark:text-gray-400">
                {lensProducts.length} produto(s) encontrado(s). Clique em um para selecionar.
              </p>

              <div className="grid gap-4">
                {lensProducts.map((product, index) => (
                  <div
                    key={index}
                    onClick={() => !specsLoading && handleSelectProduct(product)}
                    className={`flex items-start gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                      specsLoading
                        ? 'opacity-50 cursor-wait'
                        : 'hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20'
                    } ${
                      selectedProduct?.link === product.link
                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                        : 'border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    {/* Product Image */}
                    <div className="flex-shrink-0">
                      {product.thumbnail ? (
                        <img
                          src={product.thumbnail}
                          alt={product.title}
                          className="w-32 h-32 object-cover rounded-lg border border-gray-200 dark:border-gray-700"
                        />
                      ) : (
                        <div className="w-32 h-32 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center">
                          <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                    </div>

                    {/* Product Info */}
                    <div className="flex-grow min-w-0">
                      <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-lg line-clamp-2">
                        {product.title}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {product.source}
                      </p>
                      {product.price && (
                        <p className="text-lg font-bold text-green-600 dark:text-green-400 mt-2">
                          {product.price}
                        </p>
                      )}
                      <a
                        href={product.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400 mt-2 inline-block"
                      >
                        Ver no site →
                      </a>
                    </div>

                    {/* Selection indicator */}
                    <div className="flex-shrink-0">
                      {specsLoading && selectedProduct?.link === product.link ? (
                        <svg className="animate-spin h-6 w-6 text-primary-500" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                          selectedProduct?.link === product.link
                            ? 'border-primary-500 bg-primary-500'
                            : 'border-gray-300 dark:border-gray-600'
                        }`}>
                          {selectedProduct?.link === product.link && (
                            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 3: Confirm and Create Quote */}
      {lensStep === 'confirm' && selectedProduct && extractedSpecs && (
        <div className="space-y-6">
          {/* Selected Product Card */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6">
              Etapa 3: Confirmar e Criar Cotação
            </h2>

            <div className="flex flex-col lg:flex-row gap-6">
              {/* Product Image */}
              <div className="lg:w-1/3">
                {selectedProduct.thumbnail ? (
                  <img
                    src={selectedProduct.thumbnail}
                    alt={selectedProduct.title}
                    className="w-full h-64 object-contain rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
                  />
                ) : imagePreview ? (
                  <img
                    src={imagePreview}
                    alt="Imagem enviada"
                    className="w-full h-64 object-contain rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
                  />
                ) : (
                  <div className="w-full h-64 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center">
                    <svg className="w-16 h-16 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                )}
              </div>

              {/* Product Details */}
              <div className="lg:w-2/3">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">
                  {extractedSpecs.nome || selectedProduct.title}
                </h3>

                <div className="grid grid-cols-2 gap-4 mb-6">
                  {extractedSpecs.marca && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Marca</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">{extractedSpecs.marca}</p>
                    </div>
                  )}
                  {extractedSpecs.modelo && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Modelo</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">{extractedSpecs.modelo}</p>
                    </div>
                  )}
                  {extractedSpecs.tipo_produto && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Tipo</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">{extractedSpecs.tipo_produto}</p>
                    </div>
                  )}
                  {extractedSpecs.preco && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Preço de Referência</p>
                      <p className="text-green-600 dark:text-green-400 font-bold text-lg">
                        {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(extractedSpecs.preco)}
                      </p>
                    </div>
                  )}
                </div>

                {/* Specifications */}
                {extractedSpecs.especificacoes && Object.keys(extractedSpecs.especificacoes).length > 0 && (
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                    <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
                      Especificações Técnicas
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {Object.entries(extractedSpecs.especificacoes).map(([key, value]) => (
                        <div key={key} className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                            {key.replace(/_/g, ' ')}
                          </p>
                          <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                            {String(value)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Source link */}
                <div className="mt-4">
                  <a
                    href={selectedProduct.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400"
                  >
                    🔗 {selectedProduct.source} - Ver página do produto
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-4">
            <button
              onClick={handleChooseAnother}
              disabled={loading}
              className="text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            >
              ← Voltar
            </button>
            <button
              onClick={handleCreateQuote}
              disabled={loading}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Criando...' : 'Criar Cotação'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
