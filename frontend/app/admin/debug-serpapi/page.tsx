'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import AdminRoute from '@/components/AdminRoute'

interface ProductInfo {
  title: string
  price: string
  extracted_price: number | null
  source: string
  domain: string | null
  position: number
  is_blocked: boolean
  block_reason: string | null
  has_valid_price: boolean
}

interface BlockInfo {
  index: number
  size: number
  min_price: number
  max_price: number
  variation_percent: number
  products: Array<{ title: string; price: number; source: string }>
  is_valid: boolean
}

interface StepResult {
  step_number: number
  step_name: string
  description: string
  input_count: number
  output_count: number
  filtered_count: number
  details: Record<string, any> | null
}

interface ImmersiveResult {
  product_title: string
  source: string
  google_price: number
  immersive_url: string
  stores_found: number
  stores: Array<{ name: string; price: string; link: string; domain?: string; status?: string; reason?: string }>
  selected_store: { name: string; price: string; link: string; domain?: string } | null
  success: boolean
  error: string | null
}

interface ProductValidation {
  product_title: string
  product_price: number
  product_source: string
  iteration: number
  block_index: number
  step: number
  immersive_called: boolean
  stores_returned: number
  validations: Array<Record<string, any>>
  final_status: string
  failure_reason: string | null
  selected_store: Record<string, any> | null
}

interface BlockIteration {
  iteration: number
  block_size: number
  block_min_price: number
  block_max_price: number
  products_processed: number
  results_obtained: number
  results_total: number
  failures_in_iteration: number
  total_failures: number
  skipped_reasons: Record<string, number>
  status: string
  action: string
}

interface DebugResponse {
  success: boolean
  query: string
  parameters: Record<string, any>
  steps: StepResult[]
  blocks: BlockInfo[]
  immersive_results: ImmersiveResult[]
  product_validations: ProductValidation[]
  block_iterations: BlockIteration[]
  final_results: Array<Record<string, any>>
  summary: Record<string, any>
  error: string | null
}

export default function DebugSerpApiPage() {
  const [file, setFile] = useState<File | null>(null)
  const [limit, setLimit] = useState(3)
  const [variacaoMaxima, setVariacaoMaxima] = useState(25)
  const [executeImmersive, setExecuteImmersive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DebugResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set())
  const [expandedBlocks, setExpandedBlocks] = useState<Set<number>>(new Set())
  const [expandedIterations, setExpandedIterations] = useState<Set<number>>(new Set())
  const [expandedValidations, setExpandedValidations] = useState<Set<number>>(new Set())

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setResult(null)
      setError(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Selecione um arquivo JSON')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('limit', limit.toString())
      formData.append('variacao_maxima', variacaoMaxima.toString())
      formData.append('execute_immersive', executeImmersive.toString())

      const response = await api.post('/api/admin/debug-serpapi/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setResult(response.data)
      // Expandir todas as steps por padrao
      setExpandedSteps(new Set(response.data.steps.map((_: any, i: number) => i)))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao processar arquivo')
    } finally {
      setLoading(false)
    }
  }

  const toggleStep = (index: number) => {
    const newExpanded = new Set(expandedSteps)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedSteps(newExpanded)
  }

  const toggleBlock = (index: number) => {
    const newExpanded = new Set(expandedBlocks)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedBlocks(newExpanded)
  }

  const toggleIteration = (index: number) => {
    const newExpanded = new Set(expandedIterations)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedIterations(newExpanded)
  }

  const toggleValidation = (index: number) => {
    const newExpanded = new Set(expandedValidations)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedValidations(newExpanded)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'FAILED':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'CONTINUING':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'SKIPPED':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  const getActionLabel = (action: string) => {
    switch (action) {
      case 'completed':
        return 'Concluido'
      case 'recreating_blocks':
        return 'Recriando Blocos'
      case 'no_progress':
        return 'Sem Progresso'
      case 'no_products_left':
        return 'Produtos Esgotados'
      case 'no_valid_blocks':
        return 'Sem Blocos Validos'
      default:
        return action
    }
  }

  return (
    <AdminRoute>
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Debug SerpAPI
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Analise um JSON do Google Shopping e visualize cada etapa do processamento de cotação
        </p>
      </div>

      {/* Formulario */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6 mb-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Arquivo JSON do Google Shopping
            </label>
            <input
              type="file"
              accept=".json"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500 dark:text-gray-400
                file:mr-4 file:py-2 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-medium
                file:bg-primary-50 file:text-primary-700
                dark:file:bg-primary-900/30 dark:file:text-primary-300
                hover:file:bg-primary-100 dark:hover:file:bg-primary-900/50
                cursor-pointer"
            />
            {file && (
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Arquivo selecionado: {file.name}
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Número de Cotações (limit)
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 3)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Variação Máxima (%)
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={variacaoMaxima}
                onChange={(e) => setVariacaoMaxima(parseInt(e.target.value) || 25)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div className="flex items-end">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={executeImmersive}
                  onChange={(e) => setExecuteImmersive(e.target.checked)}
                  className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                  Executar Google Immersive API (chamadas reais)
                </span>
              </label>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading || !file}
              className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Processando...' : 'Analisar JSON'}
            </button>
          </div>
        </form>
      </div>

      {/* Erro */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Resultados */}
      {result && (
        <div className="space-y-6">
          {/* Resumo */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">Resumo</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {result.summary.total_raw_products}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Produtos Raw</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {result.summary.after_source_filter}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Apos Filtro Fonte</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {result.summary.after_price_filter}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Apos Filtro Preco</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {result.summary.valid_blocks}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Blocos Validos</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-primary-600 dark:text-primary-400">
                  {result.summary.quotes_obtained}/{result.summary.quotes_target}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Cotacoes Obtidas</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {result.summary.variacao_maxima}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Variacao Max</p>
              </div>
            </div>
            {result.query && (
              <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>Query:</strong> {result.query}
                </p>
              </div>
            )}
          </div>

          {/* Steps */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
              Etapas do Processamento
            </h2>
            <div className="space-y-3">
              {result.steps.map((step, index) => (
                <div
                  key={index}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
                >
                  <button
                    onClick={() => toggleStep(index)}
                    className="w-full flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary-600 text-white font-bold text-sm">
                        {step.step_number}
                      </span>
                      <div className="text-left">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {step.step_name}
                        </p>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {step.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                          {step.input_count} → {step.output_count}
                        </span>
                        {step.filtered_count > 0 && (
                          <span className="ml-2 text-sm text-red-600 dark:text-red-400">
                            (-{step.filtered_count})
                          </span>
                        )}
                      </div>
                      <svg
                        className={`w-5 h-5 transform transition-transform ${
                          expandedSteps.has(index) ? 'rotate-180' : ''
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>

                  {expandedSteps.has(index) && step.details && (
                    <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                      <pre className="text-xs text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(step.details, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Blocos de Variacao */}
          {result.blocks.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                Blocos de Variacao (Top 10)
              </h2>
              <div className="space-y-3">
                {result.blocks.map((block, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg overflow-hidden ${
                      block.is_valid
                        ? 'border-green-200 dark:border-green-800'
                        : 'border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    <button
                      onClick={() => toggleBlock(index)}
                      className={`w-full flex items-center justify-between p-4 transition-colors ${
                        block.is_valid
                          ? 'bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30'
                          : 'bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600'
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          block.is_valid
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200'
                        }`}>
                          Bloco #{block.index}
                        </span>
                        <div className="text-left">
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {block.size} produtos | R$ {block.min_price.toFixed(2)} - R$ {block.max_price.toFixed(2)}
                          </p>
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            Variacao: {block.variation_percent.toFixed(1)}%
                          </p>
                        </div>
                      </div>
                      <svg
                        className={`w-5 h-5 transform transition-transform ${
                          expandedBlocks.has(index) ? 'rotate-180' : ''
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {expandedBlocks.has(index) && (
                      <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-gray-500 dark:text-gray-400">
                              <th className="pb-2">Produto</th>
                              <th className="pb-2">Preco</th>
                              <th className="pb-2">Fonte</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                            {block.products.map((product, pIndex) => (
                              <tr key={pIndex}>
                                <td className="py-2 text-gray-900 dark:text-gray-100">
                                  {product.title}
                                </td>
                                <td className="py-2 font-medium text-gray-900 dark:text-gray-100">
                                  R$ {product.price.toFixed(2)}
                                </td>
                                <td className="py-2 text-gray-600 dark:text-gray-400">
                                  {product.source}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Iteracoes de Blocos */}
          {result.block_iterations && result.block_iterations.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                Iteracoes de Processamento (Recriacao de Blocos)
              </h2>
              <div className="space-y-3">
                {result.block_iterations.map((iteration, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg overflow-hidden ${
                      iteration.status === 'SUCCESS'
                        ? 'border-green-200 dark:border-green-800'
                        : iteration.status === 'CONTINUING'
                        ? 'border-yellow-200 dark:border-yellow-800'
                        : 'border-red-200 dark:border-red-800'
                    }`}
                  >
                    <button
                      onClick={() => toggleIteration(index)}
                      className={`w-full flex items-center justify-between p-4 transition-colors ${
                        iteration.status === 'SUCCESS'
                          ? 'bg-green-50 dark:bg-green-900/20'
                          : iteration.status === 'CONTINUING'
                          ? 'bg-yellow-50 dark:bg-yellow-900/20'
                          : 'bg-red-50 dark:bg-red-900/20'
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-gray-600 text-white font-bold text-sm">
                          {iteration.iteration}
                        </span>
                        <div className="text-left">
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            Bloco: {iteration.block_size} produtos | R$ {iteration.block_min_price.toFixed(2)} - R$ {iteration.block_max_price.toFixed(2)}
                          </p>
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            Resultados: {iteration.results_obtained} obtidos | {iteration.failures_in_iteration} falhas | Total: {iteration.results_total}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(iteration.status)}`}>
                          {iteration.status}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {getActionLabel(iteration.action)}
                        </span>
                        <svg
                          className={`w-5 h-5 transform transition-transform ${
                            expandedIterations.has(index) ? 'rotate-180' : ''
                          }`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {expandedIterations.has(index) && (
                      <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div className="bg-gray-50 dark:bg-gray-700 p-2 rounded text-center">
                            <p className="text-lg font-bold">{iteration.block_size}</p>
                            <p className="text-xs text-gray-500">Tamanho Bloco</p>
                          </div>
                          <div className="bg-gray-50 dark:bg-gray-700 p-2 rounded text-center">
                            <p className="text-lg font-bold text-green-600">{iteration.results_obtained}</p>
                            <p className="text-xs text-gray-500">Sucesso</p>
                          </div>
                          <div className="bg-gray-50 dark:bg-gray-700 p-2 rounded text-center">
                            <p className="text-lg font-bold text-red-600">{iteration.failures_in_iteration}</p>
                            <p className="text-xs text-gray-500">Falhas</p>
                          </div>
                          <div className="bg-gray-50 dark:bg-gray-700 p-2 rounded text-center">
                            <p className="text-lg font-bold">{iteration.total_failures}</p>
                            <p className="text-xs text-gray-500">Total Falhas</p>
                          </div>
                        </div>
                        {Object.keys(iteration.skipped_reasons).length > 0 && (
                          <div>
                            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Motivos dos Skips:</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(iteration.skipped_reasons).map(([reason, count]) => (
                                count > 0 && (
                                  <span key={reason} className="px-2 py-1 bg-gray-100 dark:bg-gray-600 rounded text-xs">
                                    {reason}: {count}
                                  </span>
                                )
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Validacoes Detalhadas de Produtos */}
          {result.product_validations && result.product_validations.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                Validacoes Detalhadas de Produtos ({result.product_validations.length} validacoes)
              </h2>
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {result.product_validations.map((validation, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg overflow-hidden ${
                      validation.final_status === 'SUCCESS'
                        ? 'border-green-200 dark:border-green-800'
                        : 'border-red-200 dark:border-red-800'
                    }`}
                  >
                    <button
                      onClick={() => toggleValidation(index)}
                      className={`w-full flex items-center justify-between p-3 transition-colors text-sm ${
                        validation.final_status === 'SUCCESS'
                          ? 'bg-green-50 dark:bg-green-900/20'
                          : 'bg-red-50 dark:bg-red-900/20'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-500 font-mono">#{validation.step}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(validation.final_status)}`}>
                          {validation.final_status === 'SUCCESS' ? '✓' : '✗'}
                        </span>
                        <span className="text-gray-900 dark:text-gray-100 truncate max-w-md">
                          {validation.product_title}
                        </span>
                        <span className="text-gray-500 text-xs">
                          R$ {validation.product_price.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">
                          Iter {validation.iteration}
                        </span>
                        {validation.immersive_called && (
                          <span className="text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 px-1.5 py-0.5 rounded">
                            API
                          </span>
                        )}
                        <svg
                          className={`w-4 h-4 transform transition-transform ${
                            expandedValidations.has(index) ? 'rotate-180' : ''
                          }`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {expandedValidations.has(index) && (
                      <div className="p-3 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 text-sm">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
                          <div className="text-xs">
                            <span className="text-gray-500">Fonte:</span>{' '}
                            <span className="text-gray-900 dark:text-gray-100">{validation.product_source}</span>
                          </div>
                          <div className="text-xs">
                            <span className="text-gray-500">Lojas:</span>{' '}
                            <span className="text-gray-900 dark:text-gray-100">{validation.stores_returned}</span>
                          </div>
                          <div className="text-xs">
                            <span className="text-gray-500">Immersive:</span>{' '}
                            <span className="text-gray-900 dark:text-gray-100">{validation.immersive_called ? 'Sim' : 'Nao'}</span>
                          </div>
                          {validation.failure_reason && (
                            <div className="text-xs">
                              <span className="text-gray-500">Motivo:</span>{' '}
                              <span className="text-red-600">{validation.failure_reason}</span>
                            </div>
                          )}
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Validacoes:</p>
                          {validation.validations.map((v, vIndex) => (
                            <div key={vIndex} className="text-xs bg-gray-50 dark:bg-gray-700 p-1.5 rounded flex items-center gap-2">
                              <span className="font-mono text-gray-600 dark:text-gray-400">{v.check}</span>
                              {v.passed !== undefined && (
                                <span className={v.passed ? 'text-green-600' : 'text-red-600'}>
                                  {v.passed ? '✓' : '✗'}
                                </span>
                              )}
                              {v.blocked !== undefined && (
                                <span className="text-red-600">bloqueados: {v.blocked}</span>
                              )}
                              {v.count !== undefined && (
                                <span className="text-green-600">validos: {v.count}</span>
                              )}
                              {v.stores_found !== undefined && (
                                <span className="text-blue-600">lojas: {v.stores_found}</span>
                              )}
                              {v.reason && (
                                <span className="text-gray-500">{v.reason}</span>
                              )}
                              {v.error && (
                                <span className="text-red-600">{v.error}</span>
                              )}
                            </div>
                          ))}
                        </div>
                        {validation.selected_store && (
                          <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/20 rounded">
                            <p className="text-xs font-medium text-green-800 dark:text-green-200">
                              Loja Selecionada: {validation.selected_store.name} - {validation.selected_store.price}
                            </p>
                            {validation.selected_store.domain && (
                              <p className="text-xs text-green-600">{validation.selected_store.domain}</p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resultados Immersive (resumo) */}
          {result.immersive_results.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                Resumo Chamadas Google Immersive API
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-3">Produto</th>
                      <th className="pb-3">Preco Google</th>
                      <th className="pb-3">Lojas</th>
                      <th className="pb-3">Loja Selecionada</th>
                      <th className="pb-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {result.immersive_results.map((ir, index) => (
                      <tr key={index}>
                        <td className="py-3 text-gray-900 dark:text-gray-100 max-w-xs truncate">
                          {ir.product_title}
                        </td>
                        <td className="py-3 font-medium text-gray-900 dark:text-gray-100">
                          R$ {ir.google_price.toFixed(2)}
                        </td>
                        <td className="py-3 text-gray-600 dark:text-gray-400">
                          {ir.stores_found} encontradas
                        </td>
                        <td className="py-3 text-gray-900 dark:text-gray-100">
                          {ir.selected_store ? (
                            <span>
                              {ir.selected_store.name} - {ir.selected_store.price}
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="py-3">
                          {ir.success ? (
                            <span className="px-2 py-1 rounded-full text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                              Sucesso
                            </span>
                          ) : (
                            <span className="px-2 py-1 rounded-full text-xs bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" title={ir.error || ''}>
                              Falhou
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Resultados Finais */}
          {result.final_results.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                Cotacoes Finais Obtidas
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-3">#</th>
                      <th className="pb-3">Produto</th>
                      <th className="pb-3">Preco Google</th>
                      <th className="pb-3">Loja</th>
                      <th className="pb-3">Preco Loja</th>
                      <th className="pb-3">Link</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {result.final_results.map((fr, index) => (
                      <tr key={index}>
                        <td className="py-3 text-gray-600 dark:text-gray-400">{index + 1}</td>
                        <td className="py-3 text-gray-900 dark:text-gray-100 max-w-xs truncate">
                          {fr.title}
                        </td>
                        <td className="py-3 font-medium text-gray-900 dark:text-gray-100">
                          R$ {fr.google_price?.toFixed(2)}
                        </td>
                        <td className="py-3 text-gray-900 dark:text-gray-100">
                          {fr.store}
                        </td>
                        <td className="py-3 font-medium text-green-600 dark:text-green-400">
                          {fr.store_price}
                        </td>
                        <td className="py-3">
                          {fr.store_link && (
                            <a
                              href={fr.store_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary-600 hover:text-primary-800"
                            >
                              Ver
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
    </AdminRoute>
  )
}
