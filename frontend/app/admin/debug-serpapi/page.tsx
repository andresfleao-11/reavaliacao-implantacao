'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import AdminRoute from '@/components/AdminRoute'

// =============================================================================
// INTERFACES - Nova estrutura do backend
// =============================================================================

interface FiltroAplicado {
  nome: string
  descricao: string
  entrada: number
  saida: number
  removidos: number
  detalhes?: Record<string, any>
}

interface ProdutoExtraido {
  position: number
  title: string
  source: string
  extracted_price: number | null
  has_immersive_url: boolean
  status: string
  failure_code?: string
  failure_reason?: string
}

interface BlocoFormado {
  indice: number
  tamanho: number
  preco_min: number
  preco_max: number
  variacao_percent: number
  elegivel: boolean
  potencial: number
  produtos: Array<{ position: number; title: string; price: number; source: string }>
}

interface ValidacaoProduto {
  produto_titulo: string
  produto_preco: number
  produto_source: string
  ordem_validacao: number
  sucesso: boolean
  failure_code?: string
  failure_reason?: string
  loja_selecionada?: Record<string, any>
  lojas_encontradas: number
  lojas_rejeitadas: Array<Record<string, any>>
}

interface IteracaoBloco {
  numero_iteracao: number
  tolerancia_atual: number
  tolerancia_round: number
  bloco_tamanho: number
  bloco_preco_min: number
  bloco_preco_max: number
  bloco_variacao: number
  produtos_no_bloco: number
  produtos_validados_inicio: number
  produtos_nao_testados: number
  potencial_bloco: number
  validacoes_realizadas: ValidacaoProduto[]
  novos_validados: number
  novos_descartados: number
  total_validados_apos: number
  status: string
  acao_tomada: string
  motivo?: string
}

interface ParametrosSistema {
  NUM_COTACOES: number
  VAR_MAX_PERCENT: number
  MAX_VALID_PRODUCTS: number
  INCREMENTO_VAR: number
  VALIDAR_PRECO_SITE: boolean
  DOMINIOS_BLOQUEADOS_SAMPLE: string[]
}

interface Etapa1Result {
  total_extraidos: number
  filtros_aplicados: FiltroAplicado[]
  produtos_apos_filtros: number
  blocos_formados: number
  blocos_elegiveis: number
  melhor_bloco?: BlocoFormado
  produtos_ordenados: ProdutoExtraido[]
}

interface Etapa2Result {
  iteracoes: IteracaoBloco[]
  total_iteracoes: number
  aumentos_tolerancia: number
  tolerancia_inicial: number
  tolerancia_final: number
  produtos_validados_final: number
  produtos_descartados_final: number
  sucesso: boolean
  cotacoes_obtidas: Array<Record<string, any>>
}

interface FluxoVisual {
  etapa_atual: string
  status_geral: string
  progresso: string
  resumo_fluxo: string[]
}

interface DebugResponse {
  sucesso: boolean
  query: string
  parametros: ParametrosSistema
  etapa1: Etapa1Result
  etapa2?: Etapa2Result
  fluxo_visual: FluxoVisual
  cotacoes_finais: Array<Record<string, any>>
  erro?: string
}

// =============================================================================
// COMPONENTE PRINCIPAL
// =============================================================================

export default function DebugSerpApiPage() {
  const [file, setFile] = useState<File | null>(null)
  const [limit, setLimit] = useState(3)
  const [variacaoMaxima, setVariacaoMaxima] = useState(25)
  const [executeImmersive, setExecuteImmersive] = useState(false)
  const [validarPrecoSite, setValidarPrecoSite] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DebugResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expandedFiltros, setExpandedFiltros] = useState<Set<number>>(new Set())
  const [expandedIteracoes, setExpandedIteracoes] = useState<Set<number>>(new Set())
  const [expandedValidacoes, setExpandedValidacoes] = useState<Set<string>>(new Set())
  const [showProdutos, setShowProdutos] = useState(false)

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
      formData.append('enable_price_mismatch', validarPrecoSite.toString())

      const response = await api.post('/api/admin/debug-serpapi/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setResult(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao processar arquivo')
    } finally {
      setLoading(false)
    }
  }

  const toggleFiltro = (index: number) => {
    const newExpanded = new Set(expandedFiltros)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedFiltros(newExpanded)
  }

  const toggleIteracao = (index: number) => {
    const newExpanded = new Set(expandedIteracoes)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedIteracoes(newExpanded)
  }

  const toggleValidacao = (key: string) => {
    const newExpanded = new Set(expandedValidacoes)
    if (newExpanded.has(key)) {
      newExpanded.delete(key)
    } else {
      newExpanded.add(key)
    }
    setExpandedValidacoes(newExpanded)
  }

  const getStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case 'SUCESSO':
      case 'SUCCESS':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'BLOCO_FALHOU':
      case 'FAILED':
      case 'FALHA':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'CONTINUAR':
      case 'CONTINUING':
      case 'PARCIAL':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'SIMULAÇÃO':
      case 'AGUARDANDO':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
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

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Número de Cotações
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
                  Executar Immersive API
                </span>
              </label>
            </div>

            <div className="flex items-end">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={validarPrecoSite}
                  onChange={(e) => setValidarPrecoSite(e.target.checked)}
                  className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                  Validação de Preços
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

          {/* Fluxo Visual - Status Geral */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                Status Geral
              </h2>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(result.fluxo_visual.status_geral)}`}>
                {result.fluxo_visual.status_geral}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-primary-600 dark:text-primary-400">
                  {result.fluxo_visual.progresso}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Progresso</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                  {result.etapa1.total_extraidos}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Produtos Extraídos</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                  {result.etapa1.blocos_elegiveis}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Blocos Elegíveis</p>
              </div>
            </div>

            {result.query && result.query !== 'N/A' && (
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>Query:</strong> {result.query}
                </p>
              </div>
            )}

            {/* Resumo do Fluxo */}
            <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Fluxo Executado:</p>
              <div className="space-y-1">
                {result.fluxo_visual.resumo_fluxo.map((passo, index) => (
                  <p key={index} className="text-sm text-gray-600 dark:text-gray-400 font-mono">
                    {passo}
                  </p>
                ))}
              </div>
            </div>
          </div>

          {/* Parâmetros Utilizados */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
              Parâmetros
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                <p className="text-sm text-gray-500 dark:text-gray-400">Cotações Alvo</p>
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {result.parametros.NUM_COTACOES}
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                <p className="text-sm text-gray-500 dark:text-gray-400">Variação Máxima</p>
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {result.parametros.VAR_MAX_PERCENT}%
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                <p className="text-sm text-gray-500 dark:text-gray-400">Incremento Tolerância</p>
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {result.parametros.INCREMENTO_VAR}%
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                <p className="text-sm text-gray-500 dark:text-gray-400">Validar Preço Site</p>
                <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {result.parametros.VALIDAR_PRECO_SITE ? 'Sim' : 'Não'}
                </p>
              </div>
            </div>
          </div>

          {/* ETAPA 1 - Processamento Google Shopping */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
              ETAPA 1: Processamento Google Shopping
            </h2>

            {/* Filtros Aplicados */}
            <div className="mb-6">
              <h3 className="text-md font-semibold text-gray-800 dark:text-gray-200 mb-3">
                Filtros Aplicados
              </h3>
              <div className="space-y-2">
                {result.etapa1.filtros_aplicados.map((filtro, index) => (
                  <div
                    key={index}
                    className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
                  >
                    <button
                      onClick={() => toggleFiltro(index)}
                      className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary-600 text-white text-xs font-bold">
                          {index + 1}
                        </span>
                        <div className="text-left">
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {filtro.nome}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {filtro.descricao}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right text-sm">
                          <span className="text-gray-600 dark:text-gray-400">{filtro.entrada}</span>
                          <span className="mx-1">→</span>
                          <span className="text-gray-900 dark:text-gray-100 font-medium">{filtro.saida}</span>
                          {filtro.removidos > 0 && (
                            <span className="ml-2 text-red-600 dark:text-red-400">(-{filtro.removidos})</span>
                          )}
                        </div>
                        <svg
                          className={`w-4 h-4 transform transition-transform ${expandedFiltros.has(index) ? 'rotate-180' : ''}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>
                    {expandedFiltros.has(index) && filtro.detalhes && (
                      <div className="p-3 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                        <pre className="text-xs text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">
                          {JSON.stringify(filtro.detalhes, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Resumo dos Blocos */}
            <div className="mb-6">
              <h3 className="text-md font-semibold text-gray-800 dark:text-gray-200 mb-3">
                Blocos Formados
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {result.etapa1.produtos_apos_filtros}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Produtos Válidos</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {result.etapa1.blocos_formados}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Total Blocos</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {result.etapa1.blocos_elegiveis}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Blocos Elegíveis</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-primary-600 dark:text-primary-400">
                    {result.etapa1.melhor_bloco?.tamanho || 0}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Melhor Bloco (tam)</p>
                </div>
              </div>
            </div>

            {/* Melhor Bloco */}
            {result.etapa1.melhor_bloco && (
              <div className="mb-6">
                <h3 className="text-md font-semibold text-gray-800 dark:text-gray-200 mb-3">
                  Melhor Bloco Selecionado
                </h3>
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-green-800 dark:text-green-200 font-medium">
                      Bloco #{result.etapa1.melhor_bloco.indice}
                    </span>
                    <span className="text-green-700 dark:text-green-300 text-sm">
                      {result.etapa1.melhor_bloco.tamanho} produtos | Variação: {result.etapa1.melhor_bloco.variacao_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-sm text-green-700 dark:text-green-300 mb-3">
                    Faixa de preço: R$ {result.etapa1.melhor_bloco.preco_min.toFixed(2)} - R$ {result.etapa1.melhor_bloco.preco_max.toFixed(2)}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-green-600 dark:text-green-400">
                          <th className="pb-2">#</th>
                          <th className="pb-2">Produto</th>
                          <th className="pb-2">Preço</th>
                          <th className="pb-2">Fonte</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-green-100 dark:divide-green-800">
                        {result.etapa1.melhor_bloco.produtos.slice(0, 10).map((p, index) => (
                          <tr key={index}>
                            <td className="py-1 text-green-700 dark:text-green-300">{p.position}</td>
                            <td className="py-1 text-green-800 dark:text-green-200 max-w-xs truncate">{p.title}</td>
                            <td className="py-1 font-medium text-green-800 dark:text-green-200">R$ {p.price.toFixed(2)}</td>
                            <td className="py-1 text-green-600 dark:text-green-400">{p.source}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {result.etapa1.melhor_bloco.produtos.length > 10 && (
                      <p className="text-xs text-green-600 dark:text-green-400 mt-2">
                        ... e mais {result.etapa1.melhor_bloco.produtos.length - 10} produtos
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Lista de Produtos */}
            <div>
              <button
                onClick={() => setShowProdutos(!showProdutos)}
                className="flex items-center gap-2 text-sm text-primary-600 dark:text-primary-400 hover:underline"
              >
                <svg
                  className={`w-4 h-4 transform transition-transform ${showProdutos ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
                {showProdutos ? 'Ocultar' : 'Ver'} lista de produtos ({result.etapa1.produtos_ordenados.length})
              </button>
              {showProdutos && (
                <div className="mt-3 overflow-x-auto max-h-[400px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-white dark:bg-gray-800">
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b">
                        <th className="pb-2 px-2">#</th>
                        <th className="pb-2 px-2">Produto</th>
                        <th className="pb-2 px-2">Preço</th>
                        <th className="pb-2 px-2">Fonte</th>
                        <th className="pb-2 px-2">Immersive</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {result.etapa1.produtos_ordenados.map((p, index) => (
                        <tr key={index}>
                          <td className="py-1 px-2 text-gray-600">{p.position}</td>
                          <td className="py-1 px-2 text-gray-900 dark:text-gray-100 max-w-xs truncate">{p.title}</td>
                          <td className="py-1 px-2 font-medium">R$ {p.extracted_price?.toFixed(2) || '-'}</td>
                          <td className="py-1 px-2 text-gray-600 dark:text-gray-400">{p.source}</td>
                          <td className="py-1 px-2">
                            {p.has_immersive_url ? (
                              <span className="text-green-600">✓</span>
                            ) : (
                              <span className="text-red-600">✗</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* ETAPA 2 - Validação de Bloco */}
          {result.etapa2 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                ETAPA 2: Validação de Bloco (Immersive API)
              </h2>

              {/* Resumo da Etapa 2 */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {result.etapa2.total_iteracoes}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Iterações</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {result.etapa2.produtos_validados_final}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Validados</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                    {result.etapa2.produtos_descartados_final}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Descartados</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                    {result.etapa2.aumentos_tolerancia}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Aumentos Tolerância</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg text-center">
                  <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                    {result.etapa2.tolerancia_inicial}% → {result.etapa2.tolerancia_final.toFixed(0)}%
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Tolerância (ini → fin)</p>
                </div>
              </div>

              {/* Iterações */}
              <h3 className="text-md font-semibold text-gray-800 dark:text-gray-200 mb-3">
                Iterações de Validação
              </h3>
              <div className="space-y-2">
                {result.etapa2.iteracoes.map((iteracao, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg overflow-hidden ${
                      iteracao.status === 'SUCESSO'
                        ? 'border-green-200 dark:border-green-800'
                        : iteracao.status === 'BLOCO_FALHOU'
                        ? 'border-red-200 dark:border-red-800'
                        : 'border-yellow-200 dark:border-yellow-800'
                    }`}
                  >
                    <button
                      onClick={() => toggleIteracao(index)}
                      className={`w-full flex items-center justify-between p-3 transition-colors ${
                        iteracao.status === 'SUCESSO'
                          ? 'bg-green-50 dark:bg-green-900/20'
                          : iteracao.status === 'BLOCO_FALHOU'
                          ? 'bg-red-50 dark:bg-red-900/20'
                          : 'bg-yellow-50 dark:bg-yellow-900/20'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-gray-600 text-white text-sm font-bold">
                          {iteracao.numero_iteracao}
                        </span>
                        <div className="text-left">
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            Bloco: {iteracao.bloco_tamanho} prod | R$ {iteracao.bloco_preco_min.toFixed(2)} - R$ {iteracao.bloco_preco_max.toFixed(2)}
                          </p>
                          <p className="text-xs text-gray-600 dark:text-gray-400">
                            Potencial: {iteracao.potencial_bloco} | Tolerância: {iteracao.tolerancia_atual.toFixed(0)}%
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-right text-xs">
                          <span className="text-green-600">+{iteracao.novos_validados}</span>
                          <span className="mx-1">/</span>
                          <span className="text-red-600">-{iteracao.novos_descartados}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(iteracao.status)}`}>
                          {iteracao.status}
                        </span>
                        <svg
                          className={`w-4 h-4 transform transition-transform ${expandedIteracoes.has(index) ? 'rotate-180' : ''}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {expandedIteracoes.has(index) && (
                      <div className="p-3 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                          <strong>Ação:</strong> {iteracao.acao_tomada}
                        </p>

                        {/* Validações da iteração */}
                        <div className="space-y-1">
                          {iteracao.validacoes_realizadas.map((val, vIndex) => {
                            const valKey = `${index}-${vIndex}`
                            return (
                              <div
                                key={vIndex}
                                className={`border rounded overflow-hidden ${
                                  val.sucesso ? 'border-green-200' : 'border-red-200'
                                }`}
                              >
                                <button
                                  onClick={() => toggleValidacao(valKey)}
                                  className={`w-full flex items-center justify-between p-2 text-xs ${
                                    val.sucesso ? 'bg-green-50 dark:bg-green-900/10' : 'bg-red-50 dark:bg-red-900/10'
                                  }`}
                                >
                                  <div className="flex items-center gap-2">
                                    <span className={`font-medium ${val.sucesso ? 'text-green-600' : 'text-red-600'}`}>
                                      {val.sucesso ? '✓' : '✗'}
                                    </span>
                                    <span className="text-gray-900 dark:text-gray-100 max-w-md truncate">
                                      {val.produto_titulo}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className="text-gray-500">R$ {val.produto_preco.toFixed(2)}</span>
                                    {val.failure_code && (
                                      <span className="text-red-600 text-xs">{val.failure_code}</span>
                                    )}
                                    <svg
                                      className={`w-3 h-3 transform transition-transform ${expandedValidacoes.has(valKey) ? 'rotate-180' : ''}`}
                                      fill="none"
                                      stroke="currentColor"
                                      viewBox="0 0 24 24"
                                    >
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                  </div>
                                </button>
                                {expandedValidacoes.has(valKey) && (
                                  <div className="p-2 text-xs bg-white dark:bg-gray-800 border-t">
                                    <p><strong>Fonte:</strong> {val.produto_source}</p>
                                    <p><strong>Lojas encontradas:</strong> {val.lojas_encontradas}</p>
                                    {val.failure_reason && (
                                      <p className="text-red-600"><strong>Motivo:</strong> {val.failure_reason}</p>
                                    )}
                                    {val.loja_selecionada && (
                                      <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/20 rounded">
                                        <p className="font-medium text-green-800 dark:text-green-200">
                                          Loja: {val.loja_selecionada.name}
                                        </p>
                                        <p className="text-green-600 text-xs truncate">{val.loja_selecionada.link}</p>
                                      </div>
                                    )}
                                    {val.lojas_rejeitadas.length > 0 && (
                                      <div className="mt-2">
                                        <p className="font-medium text-gray-700 dark:text-gray-300">Lojas rejeitadas:</p>
                                        {val.lojas_rejeitadas.slice(0, 5).map((loja, lIndex) => (
                                          <p key={lIndex} className="text-red-600 text-xs">
                                            {loja.name}: {loja.rejection}
                                          </p>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Cotações Finais */}
          {result.cotacoes_finais.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
                Cotações Finais Obtidas ({result.cotacoes_finais.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-3">#</th>
                      <th className="pb-3">Produto</th>
                      <th className="pb-3">Preço Google</th>
                      <th className="pb-3">Loja</th>
                      <th className="pb-3">Domínio</th>
                      <th className="pb-3">Link</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {result.cotacoes_finais.map((cotacao, index) => (
                      <tr key={index}>
                        <td className="py-3 text-gray-600 dark:text-gray-400">{index + 1}</td>
                        <td className="py-3 text-gray-900 dark:text-gray-100 max-w-xs truncate">
                          {cotacao.titulo}
                        </td>
                        <td className="py-3 font-medium text-gray-900 dark:text-gray-100">
                          R$ {cotacao.preco_google?.toFixed(2)}
                        </td>
                        <td className="py-3 text-gray-900 dark:text-gray-100">
                          {cotacao.loja}
                        </td>
                        <td className="py-3 text-gray-600 dark:text-gray-400 text-xs">
                          {cotacao.dominio}
                        </td>
                        <td className="py-3">
                          {cotacao.url && (
                            <a
                              href={cotacao.url}
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

          {/* Erro */}
          {result.erro && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg">
              <strong>Erro:</strong> {result.erro}
            </div>
          )}
        </div>
      )}
    </div>
    </AdminRoute>
  )
}
