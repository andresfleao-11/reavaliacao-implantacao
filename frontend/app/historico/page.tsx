'use client'

import { useState } from 'react'
import Link from 'next/link'
import useSWR from 'swr'
import { quotesApi } from '@/lib/api'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

export default function HistoricoPage() {
  const [page, setPage] = useState(1)
  const perPage = 20

  const { data, error, mutate } = useSWR(
    `/quotes?page=${page}`,
    () => quotesApi.list(page, perPage),
    {
      // Atualiza a cada 5 segundos se houver alguma cotação em processamento
      refreshInterval: (data) => {
        const hasProcessing = data?.items?.some((q: any) => q.status === 'PROCESSING')
        return hasProcessing ? 5000 : 0
      },
      // Também atualiza quando a janela recebe foco
      revalidateOnFocus: true,
    }
  )

  const formatCurrency = (value: number | null) => {
    if (value === null) return 'N/A'
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(value)
  }

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })
  }

  const totalPages = data ? Math.ceil(data.total / perPage) : 0

  return (
    <div className="max-w-7xl">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Histórico de Cotações</h1>
        <Link href="/cotacao" className="btn-primary">
          Nova Cotação
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg mb-6">
          Erro ao carregar cotações
        </div>
      )}

      {!data && !error && (
        <div className="card">
          <p className="text-gray-600 dark:text-gray-400">Carregando...</p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-gray-600 dark:text-gray-400 mb-4">Nenhuma cotação encontrada</p>
          <Link href="/cotacao" className="btn-primary">
            Criar primeira cotação
          </Link>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="card overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Código
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Descrição
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Projeto
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Data
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Valor Médio
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {data.items.map((quote) => (
                  <tr key={quote.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-gray-100">
                      #{quote.id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {quote.codigo_item || '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                      {quote.nome_item || 'Sem descrição'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                      {quote.project_nome ? (
                        <Link
                          href={`/cadastros/projetos/${quote.project_id}`}
                          className="hover:text-primary-600 dark:hover:text-primary-400"
                        >
                          <div className="font-medium">{quote.project_nome}</div>
                          {quote.cliente_nome && (
                            <div className="text-xs text-gray-400 dark:text-gray-500">{quote.cliente_nome}</div>
                          )}
                        </Link>
                      ) : (
                        <span className="text-gray-400 dark:text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(quote.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {formatCurrency(quote.valor_medio)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs rounded-full ${
                          quote.status === 'DONE'
                            ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                            : quote.status === 'PROCESSING'
                            ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
                            : quote.status === 'CANCELLED'
                            ? 'bg-gray-100 dark:bg-gray-900/30 text-gray-800 dark:text-gray-300'
                            : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
                        }`}
                      >
                        {quote.status === 'DONE' ? 'Concluída' : quote.status === 'PROCESSING' ? 'Processando' : quote.status === 'CANCELLED' ? 'Cancelada' : 'Erro'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <Link
                        href={`/cotacao/${quote.id}`}
                        className="text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 font-medium"
                      >
                        Ver detalhes
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-6 flex justify-center space-x-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800"
              >
                Anterior
              </button>

              <div className="flex items-center px-4 py-2 text-gray-700 dark:text-gray-300">
                Página {page} de {totalPages}
              </div>

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800"
              >
                Próxima
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
