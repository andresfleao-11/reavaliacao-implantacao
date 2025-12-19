'use client'

import { useState } from 'react'

interface SearchLogDetailProps {
  searchStats: any
  shoppingLog: any
}

export default function SearchLogDetail({ searchStats, shoppingLog }: SearchLogDetailProps) {
  const [etapa1Expanded, setEtapa1Expanded] = useState(true)
  const [etapa2Expanded, setEtapa2Expanded] = useState(true)
  const [failuresExpanded, setFailuresExpanded] = useState(false)
  const [successExpanded, setSuccessExpanded] = useState(false)
  const [expandedFailures, setExpandedFailures] = useState<Set<number>>(new Set())
  const [expandedIterations, setExpandedIterations] = useState<Set<number>>(new Set())

  // Extrair parâmetros
  const params = searchStats.parameters || {}
  const numCotacoes = params.num_cotacoes || searchStats.quotes_target || 3
  const varMaxPercent = params.variacao_maxima || 25
  const validarPreco = searchStats.enable_price_mismatch !== false

  // Calcular estatísticas da ETAPA 1
  const totalExtraidos = shoppingLog.total_raw_products || 0
  const aposFiltroDominio = shoppingLog.after_source_filter || 0
  const aposOrdLimite = searchStats.products_available_for_blocks || aposFiltroDominio

  // Status labels
  const failureStepLabels: Record<string, string> = {
    'IMMERSIVE_API': 'API Immersive',
    'URL_VALIDATION': 'Validacao URL',
    'PRICE_EXTRACTION': 'Extracao Preco',
    'PRICE_VALIDATION': 'Validacao Preco',
    'SCREENSHOT_CAPTURE': 'Screenshot',
    'PAGE_LOAD': 'Carregamento',
    'UNKNOWN': 'Desconhecido'
  }

  const failureCodeLabels: Record<string, string> = {
    'NO_STORE_LINK': 'Sem link de loja',
    'BLOCKED_DOMAIN': 'Dominio bloqueado',
    'FOREIGN_DOMAIN': 'Dominio estrangeiro',
    'DUPLICATE_URL': 'URL duplicada',
    'LISTING_URL': 'URL de listagem',
    'PRICE_MISMATCH': 'Preco divergente',
    'EXTRACTION_ERROR': 'Erro de extracao',
    'API_ERROR': 'Erro de API'
  }

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'SUCCESS':
      case 'SUCESSO':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'FAILED':
      case 'FALHA':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'BLOCK_FAILED':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  return (
    <div className="space-y-6">
      {/* ============================================= */}
      {/* PARAMETROS DO SISTEMA */}
      {/* ============================================= */}
      <div className="bg-gradient-to-r from-gray-50 to-slate-50 dark:from-gray-800 dark:to-slate-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 mb-3 flex items-center gap-2">
          <span className="bg-gray-600 text-white px-2 py-0.5 rounded text-xs">PARAMETROS</span>
          Configuracao da Cotacao
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white dark:bg-gray-700 rounded-lg p-3 border border-gray-200 dark:border-gray-600">
            <p className="text-xs text-gray-500 dark:text-gray-400">NUM_COTACOES</p>
            <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{numCotacoes}</p>
            <p className="text-[10px] text-gray-400">Cotacoes necessarias</p>
          </div>
          <div className="bg-white dark:bg-gray-700 rounded-lg p-3 border border-gray-200 dark:border-gray-600">
            <p className="text-xs text-gray-500 dark:text-gray-400">VAR_MAX_PERCENT</p>
            <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{varMaxPercent}%</p>
            <p className="text-[10px] text-gray-400">Variacao maxima</p>
          </div>
          <div className="bg-white dark:bg-gray-700 rounded-lg p-3 border border-gray-200 dark:border-gray-600">
            <p className="text-xs text-gray-500 dark:text-gray-400">VALIDAR_PRECO</p>
            <p className={`text-xl font-bold ${validarPreco ? 'text-green-600' : 'text-yellow-600'}`}>
              {validarPreco ? 'SIM' : 'NAO'}
            </p>
            <p className="text-[10px] text-gray-400">Verificar preco site</p>
          </div>
          <div className="bg-white dark:bg-gray-700 rounded-lg p-3 border border-gray-200 dark:border-gray-600">
            <p className="text-xs text-gray-500 dark:text-gray-400">FONTE PRECO</p>
            <p className="text-lg font-bold text-gray-900 dark:text-gray-100 font-mono">
              {searchStats.price_source || (validarPreco ? 'site' : 'google')}
            </p>
            <p className="text-[10px] text-gray-400">Origem do valor</p>
          </div>
        </div>
      </div>

      {/* ============================================= */}
      {/* ETAPA 1: PROCESSAMENTO GOOGLE SHOPPING */}
      {/* ============================================= */}
      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 overflow-hidden">
        <button
          onClick={() => setEtapa1Expanded(!etapa1Expanded)}
          className="w-full flex items-center justify-between p-4 hover:bg-blue-100/50 dark:hover:bg-blue-900/30 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-bold">ETAPA 1</span>
            <span className="text-blue-800 dark:text-blue-200 font-semibold">Processamento Google Shopping</span>
          </div>
          <svg className={`w-5 h-5 text-blue-600 transform transition-transform ${etapa1Expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {etapa1Expanded && (
          <div className="p-4 pt-0 space-y-4">
            {/* Funil de Filtros */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Funil de Filtragem</h4>
              <div className="flex items-center justify-between text-center">
                <div className="flex-1">
                  <div className="bg-blue-100 dark:bg-blue-900/40 rounded-lg p-3">
                    <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{totalExtraidos}</p>
                    <p className="text-xs text-blue-600 dark:text-blue-400">Extraidos</p>
                  </div>
                </div>
                <div className="px-2 text-gray-400">→</div>
                <div className="flex-1">
                  <div className="bg-yellow-100 dark:bg-yellow-900/40 rounded-lg p-3">
                    <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">{aposFiltroDominio}</p>
                    <p className="text-xs text-yellow-600 dark:text-yellow-400">Filtro Dominio</p>
                    {totalExtraidos > 0 && (
                      <p className="text-[10px] text-red-500">-{totalExtraidos - aposFiltroDominio}</p>
                    )}
                  </div>
                </div>
                <div className="px-2 text-gray-400">→</div>
                <div className="flex-1">
                  <div className="bg-green-100 dark:bg-green-900/40 rounded-lg p-3">
                    <p className="text-2xl font-bold text-green-700 dark:text-green-300">{aposOrdLimite}</p>
                    <p className="text-xs text-green-600 dark:text-green-400">Para Blocos</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Blocos Formados */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Formacao de Blocos</h4>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
                  <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{searchStats.blocks_recalculated || 0}</p>
                  <p className="text-xs text-purple-600 dark:text-purple-400">Blocos Calculados</p>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
                  <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{searchStats.eligible_blocks || '-'}</p>
                  <p className="text-xs text-purple-600 dark:text-purple-400">Blocos Elegiveis</p>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
                  <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{searchStats.products_tested || 0}</p>
                  <p className="text-xs text-purple-600 dark:text-purple-400">Produtos Testados</p>
                </div>
              </div>
            </div>

            {/* Lista inicial de produtos ordenados */}
            {searchStats.initial_products_sorted && searchStats.initial_products_sorted.length > 0 && (
              <details className="bg-white dark:bg-gray-800 rounded-lg overflow-hidden">
                <summary className="p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Lista de Produtos Ordenados ({searchStats.initial_products_sorted.length})
                  </span>
                  <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </summary>
                <div className="max-h-64 overflow-y-auto border-t border-gray-200 dark:border-gray-700">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 dark:bg-gray-700 sticky top-0">
                      <tr>
                        <th className="px-2 py-1 text-left">#</th>
                        <th className="px-2 py-1 text-left">Produto</th>
                        <th className="px-2 py-1 text-left">Fonte</th>
                        <th className="px-2 py-1 text-right">Preco</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {searchStats.initial_products_sorted.map((p: any) => (
                        <tr key={p.index} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <td className="px-2 py-1 font-mono">{p.index}</td>
                          <td className="px-2 py-1 truncate max-w-[200px]" title={p.title}>{p.title}</td>
                          <td className="px-2 py-1 text-gray-500">{p.source}</td>
                          <td className="px-2 py-1 text-right font-mono">R$ {p.price?.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      {/* ============================================= */}
      {/* ETAPA 2: VALIDACAO DE BLOCO */}
      {/* ============================================= */}
      <div className="bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800 overflow-hidden">
        <button
          onClick={() => setEtapa2Expanded(!etapa2Expanded)}
          className="w-full flex items-center justify-between p-4 hover:bg-green-100/50 dark:hover:bg-green-900/30 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="bg-green-600 text-white px-3 py-1 rounded-lg text-sm font-bold">ETAPA 2</span>
            <span className="text-green-800 dark:text-green-200 font-semibold">Validacao de Bloco (API Immersive)</span>
          </div>
          <svg className={`w-5 h-5 text-green-600 transform transition-transform ${etapa2Expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {etapa2Expanded && (
          <div className="p-4 pt-0 space-y-4">
            {/* Resumo da Validacao */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Resumo da Validacao</h4>
              <div className="grid grid-cols-4 gap-3 text-center">
                <div className="bg-green-100 dark:bg-green-900/40 rounded-lg p-3">
                  <p className="text-2xl font-bold text-green-700 dark:text-green-300">{searchStats.final_valid_sources || 0}</p>
                  <p className="text-xs text-green-600 dark:text-green-400">Validados</p>
                </div>
                <div className="bg-red-100 dark:bg-red-900/40 rounded-lg p-3">
                  <p className="text-2xl font-bold text-red-700 dark:text-red-300">{searchStats.final_failed_products || 0}</p>
                  <p className="text-xs text-red-600 dark:text-red-400">Falharam</p>
                </div>
                <div className="bg-blue-100 dark:bg-blue-900/40 rounded-lg p-3">
                  <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{searchStats.immersive_api_calls || 0}</p>
                  <p className="text-xs text-blue-600 dark:text-blue-400">Chamadas API</p>
                </div>
                <div className="bg-purple-100 dark:bg-purple-900/40 rounded-lg p-3">
                  <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{searchStats.tolerance_increases || 0}</p>
                  <p className="text-xs text-purple-600 dark:text-purple-400">Aum. Tolerancia</p>
                </div>
              </div>
            </div>

            {/* Aumentos de Tolerancia */}
            {searchStats.tolerance_increases > 0 && (
              <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-4 border border-yellow-200 dark:border-yellow-800">
                <h4 className="text-sm font-semibold text-yellow-800 dark:text-yellow-200 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  Aumentos de Tolerancia ({searchStats.tolerance_increases}x)
                </h4>
                <div className="space-y-3">
                  {/* Mostrar progressão da tolerância */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 px-2 py-1 rounded text-xs font-medium">
                      Inicial: {searchStats.initial_tolerance || 25}%
                    </span>
                    {Array.from({ length: searchStats.tolerance_increases || 0 }, (_, i) => (
                      <span key={i} className="flex items-center gap-1">
                        <svg className="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                        </svg>
                        <span className="bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200 px-2 py-1 rounded text-xs font-medium">
                          {(searchStats.initial_tolerance || 25) + ((i + 1) * 5)}%
                        </span>
                      </span>
                    ))}
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      <span className="bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 px-2 py-1 rounded text-xs font-medium">
                        Final: {searchStats.final_tolerance || ((searchStats.initial_tolerance || 25) + (searchStats.tolerance_increases || 0) * 5)}%
                      </span>
                    </span>
                  </div>

                  {/* Mostrar blocos que falharam em cada tolerância (agrupados) */}
                  {searchStats.block_history && searchStats.block_history.length > 0 && (
                    <div className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">
                      <p className="font-medium mb-1">Blocos por nivel de tolerancia:</p>
                      {(() => {
                        // Agrupar blocos por tolerance_round
                        const blocksByTolerance: { [key: number]: any[] } = {}
                        searchStats.block_history.forEach((block: any) => {
                          const round = block.tolerance_round || 0
                          if (!blocksByTolerance[round]) blocksByTolerance[round] = []
                          blocksByTolerance[round].push(block)
                        })

                        return Object.entries(blocksByTolerance).map(([round, blocks]) => {
                          const tolerance = (searchStats.initial_tolerance || 25) + (parseInt(round) * 5)
                          const failedBlocks = blocks.filter((b: any) => b.result === 'failed')
                          const successBlocks = blocks.filter((b: any) => b.result === 'success' || b.result === 'success_early')

                          return (
                            <div key={round} className="ml-2 mb-1">
                              <span className="font-medium">Tolerancia {tolerance}%:</span>{' '}
                              {blocks.length} bloco(s) testado(s)
                              {failedBlocks.length > 0 && (
                                <span className="text-red-600 dark:text-red-400"> ({failedBlocks.length} falharam)</span>
                              )}
                              {successBlocks.length > 0 && (
                                <span className="text-green-600 dark:text-green-400"> ({successBlocks.length} sucesso)</span>
                              )}
                            </div>
                          )
                        })
                      })()}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Historico de Iteracoes */}
            {searchStats.block_history && searchStats.block_history.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                  Iteracoes de Validacao ({searchStats.block_history.length})
                </h4>
                <div className="space-y-2">
                  {searchStats.block_history.map((block: any, idx: number) => {
                    const isExpanded = expandedIterations.has(idx)
                    // Extrair testes de sucesso e falha
                    const tests = block.tests || []
                    const successTests = tests.filter((t: any) => t.result === 'success')
                    const failedTests = tests.filter((t: any) => t.result === 'failed')
                    // Calcular variacao
                    const minPrice = block.price_range?.min || 0
                    const maxPrice = block.price_range?.max || 0
                    const variation = minPrice > 0 ? ((maxPrice - minPrice) / minPrice) * 100 : 0

                    return (
                      <div key={idx} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                        <button
                          onClick={() => {
                            const newSet = new Set(expandedIterations)
                            if (isExpanded) newSet.delete(idx)
                            else newSet.add(idx)
                            setExpandedIterations(newSet)
                          }}
                          className={`w-full flex items-center justify-between p-3 text-left transition-colors ${
                            block.result === 'success' || block.result === 'success_early' ? 'bg-green-50 dark:bg-green-900/20' :
                            block.result === 'failed' ? 'bg-orange-50 dark:bg-orange-900/20' :
                            'bg-gray-50 dark:bg-gray-700'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="bg-gray-600 text-white text-xs font-bold px-2 py-1 rounded">
                              #{block.iteration}
                            </span>
                            <div>
                              <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                                Bloco [{block.products_indices?.join(', ')}]
                              </span>
                              <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                                {block.block_size || 0} produtos | Var: {variation.toFixed(1)}%
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {successTests.length > 0 && (
                              <span className="text-xs text-green-600">+{successTests.length} validados</span>
                            )}
                            {failedTests.length > 0 && (
                              <span className="text-xs text-red-600">-{failedTests.length} falhas</span>
                            )}
                            <span className={`px-2 py-0.5 text-xs rounded ${getStatusColor(block.result)}`}>
                              {block.result === 'success' || block.result === 'success_early' ? 'SUCESSO' : block.result === 'failed' ? 'BLOCO FALHOU' : block.result}
                            </span>
                            <svg className={`w-4 h-4 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="p-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
                            {/* Info do Bloco */}
                            <div className="grid grid-cols-4 gap-2 mb-3 text-xs">
                              <div className="bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                <span className="text-gray-500">Preco Min:</span>
                                <span className="font-mono ml-1">R$ {minPrice.toFixed(2)}</span>
                              </div>
                              <div className="bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                <span className="text-gray-500">Preco Max:</span>
                                <span className="font-mono ml-1">R$ {maxPrice.toFixed(2)}</span>
                              </div>
                              <div className="bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                <span className="text-gray-500">Variacao:</span>
                                <span className="font-mono ml-1">{variation.toFixed(1)}%</span>
                              </div>
                              <div className="bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                <span className="text-gray-500">Tolerancia:</span>
                                <span className="font-mono ml-1">{block.var_max_percent?.toFixed(0) || 25}%</span>
                              </div>
                            </div>

                            {/* Produtos do Bloco */}
                            {block.products_in_block?.length > 0 && (
                              <div className="mb-3">
                                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Produtos no Bloco:</p>
                                <div className="flex flex-wrap gap-1">
                                  {block.products_in_block.map((p: any, pIdx: number) => (
                                    <span key={pIdx} className={`text-[10px] px-2 py-0.5 rounded ${
                                      p.status === 'validated' ? 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200' :
                                      p.status === 'failed' ? 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200' :
                                      'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
                                    }`} title={p.title}>
                                      #{p.index} {p.source} R$ {p.price?.toFixed(2)}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Testes Realizados */}
                            {tests.length > 0 && (
                              <div className="mb-2">
                                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Testes Realizados ({tests.length}):</p>
                                <div className="space-y-1 max-h-40 overflow-y-auto">
                                  {tests.map((t: any, tIdx: number) => (
                                    <div key={tIdx} className={`text-[10px] p-2 rounded ${
                                      t.result === 'success' ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'
                                    }`}>
                                      <div className="flex justify-between items-start">
                                        <span className="font-medium">#{t.product_index} {t.source}</span>
                                        <span className={`px-1.5 py-0.5 rounded ${
                                          t.result === 'success' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'
                                        }`}>
                                          {t.result === 'success' ? 'OK' : 'FALHA'}
                                        </span>
                                      </div>
                                      <div className="text-gray-600 dark:text-gray-400 truncate" title={t.title}>{t.title}</div>
                                      {t.result === 'success' ? (
                                        <div className="text-green-600">
                                          R$ {t.google_price?.toFixed(2)} → R$ {t.final_price?.toFixed(2)} ({t.domain})
                                        </div>
                                      ) : (
                                        <div className="text-red-600">
                                          {t.failure_step}: {t.error_message}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Status Final do Bloco */}
                            {block.status_after && (
                              <div className="mt-2 text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 p-2 rounded">
                                <span className="font-medium">Resultado:</span> {block.status_after.valid_count || 0} validados |
                                +{block.status_after.successes_this_block || 0} sucessos |
                                -{block.status_after.failures_this_block || 0} falhas nesta iteracao
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

            {/* Tabela de Falhas */}
            {searchStats.validation_failures && searchStats.validation_failures.length > 0 && (
              <details className="bg-white dark:bg-gray-800 rounded-lg overflow-hidden" open={failuresExpanded}>
                <summary
                  onClick={(e) => { e.preventDefault(); setFailuresExpanded(!failuresExpanded) }}
                  className="p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between"
                >
                  <span className="text-sm font-medium text-red-700 dark:text-red-300 flex items-center gap-2">
                    <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                    Produtos que Falharam ({searchStats.validation_failures.length})
                  </span>
                  <svg className={`w-4 h-4 text-gray-500 transform transition-transform ${failuresExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="border-t border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 dark:bg-gray-700 sticky top-0">
                      <tr>
                        <th className="px-2 py-2 text-left">#</th>
                        <th className="px-2 py-2 text-left">Produto</th>
                        <th className="px-2 py-2 text-left">Fonte</th>
                        <th className="px-2 py-2 text-right">Preco</th>
                        <th className="px-2 py-2 text-center">Codigo Falha</th>
                        <th className="px-2 py-2 text-center">Etapa</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {searchStats.validation_failures.map((f: any, idx: number) => (
                        <tr key={idx} className="hover:bg-red-50 dark:hover:bg-red-900/10">
                          <td className="px-2 py-2">{idx + 1}</td>
                          <td className="px-2 py-2 truncate max-w-[150px]" title={f.title}>{f.title}</td>
                          <td className="px-2 py-2 text-gray-500">{f.source}</td>
                          <td className="px-2 py-2 text-right font-mono">R$ {f.google_price?.toFixed(2)}</td>
                          <td className="px-2 py-2 text-center">
                            <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 rounded text-[10px]">
                              {failureCodeLabels[f.failure_code] || f.failure_code || f.error_message?.substring(0, 20)}
                            </span>
                          </td>
                          <td className="px-2 py-2 text-center text-gray-500">
                            {failureStepLabels[f.failure_step] || f.failure_step}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            {/* Tabela de Sucessos */}
            {searchStats.successful_products && searchStats.successful_products.length > 0 && (
              <details className="bg-white dark:bg-gray-800 rounded-lg overflow-hidden" open={successExpanded}>
                <summary
                  onClick={(e) => { e.preventDefault(); setSuccessExpanded(!successExpanded) }}
                  className="p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between"
                >
                  <span className="text-sm font-medium text-green-700 dark:text-green-300 flex items-center gap-2">
                    <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                    Produtos Validados com Sucesso ({searchStats.successful_products.length})
                  </span>
                  <svg className={`w-4 h-4 text-gray-500 transform transition-transform ${successExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="border-t border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 dark:bg-gray-700 sticky top-0">
                      <tr>
                        <th className="px-2 py-2 text-left">#</th>
                        <th className="px-2 py-2 text-left">Produto</th>
                        <th className="px-2 py-2 text-left">Dominio</th>
                        <th className="px-2 py-2 text-right">Preco Google</th>
                        <th className="px-2 py-2 text-right">Preco Extraido</th>
                        <th className="px-2 py-2 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {searchStats.successful_products.map((p: any, idx: number) => (
                        <tr key={idx} className="hover:bg-green-50 dark:hover:bg-green-900/10">
                          <td className="px-2 py-2">{idx + 1}</td>
                          <td className="px-2 py-2 truncate max-w-[150px]" title={p.title}>{p.title}</td>
                          <td className="px-2 py-2 text-gray-500">{p.domain}</td>
                          <td className="px-2 py-2 text-right font-mono">R$ {p.google_price?.toFixed(2)}</td>
                          <td className="px-2 py-2 text-right font-mono text-green-600 dark:text-green-400">R$ {p.extracted_price?.toFixed(2)}</td>
                          <td className="px-2 py-2 text-center">
                            <span className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded text-[10px]">
                              OK
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      {/* ============================================= */}
      {/* FLUXO VISUAL - RESUMO */}
      {/* ============================================= */}
      <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
        <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3">Resumo do Fluxo</h4>
        <div className="flex items-center justify-center gap-2 text-xs">
          <div className="text-center">
            <div className="bg-blue-500 text-white rounded-lg px-3 py-2 font-bold">{totalExtraidos}</div>
            <div className="text-gray-500 mt-1">Google</div>
          </div>
          <div className="text-gray-400">→</div>
          <div className="text-center">
            <div className="bg-yellow-500 text-white rounded-lg px-3 py-2 font-bold">{aposFiltroDominio}</div>
            <div className="text-gray-500 mt-1">Filtrado</div>
          </div>
          <div className="text-gray-400">→</div>
          <div className="text-center">
            <div className="bg-purple-500 text-white rounded-lg px-3 py-2 font-bold">{searchStats.products_tested || 0}</div>
            <div className="text-gray-500 mt-1">Testados</div>
          </div>
          <div className="text-gray-400">→</div>
          <div className="text-center">
            <div className="bg-green-500 text-white rounded-lg px-3 py-2 font-bold">{searchStats.final_valid_sources || 0}</div>
            <div className="text-gray-500 mt-1">Validados</div>
          </div>
          <div className="text-gray-400">=</div>
          <div className="text-center">
            <div className={`rounded-lg px-3 py-2 font-bold ${
              (searchStats.final_valid_sources || 0) >= numCotacoes
                ? 'bg-green-600 text-white'
                : 'bg-red-500 text-white'
            }`}>
              {(searchStats.final_valid_sources || 0) >= numCotacoes ? 'SUCESSO' : 'FALHA'}
            </div>
            <div className="text-gray-500 mt-1">{searchStats.final_valid_sources || 0}/{numCotacoes}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
