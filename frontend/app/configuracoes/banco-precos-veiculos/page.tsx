'use client'

import { useState, useEffect } from 'react'
import { vehiclePricesApi, VehiclePrice, VehiclePriceListResponse } from '@/lib/api'

export default function BancoPrecoVeiculosPage() {
  // Data state
  const [data, setData] = useState<VehiclePriceListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters state
  const [brands, setBrands] = useState<string[]>([])
  const [years, setYears] = useState<number[]>([])
  const [referenceMonths, setReferenceMonths] = useState<string[]>([])

  // Filter values
  const [selectedBrand, setSelectedBrand] = useState<string>('')
  const [selectedYear, setSelectedYear] = useState<string>('')
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [selectedStatus, setSelectedStatus] = useState<string>('')
  const [searchFipe, setSearchFipe] = useState<string>('')
  const [searchModel, setSearchModel] = useState<string>('')

  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize] = useState(15)

  // Actions state
  const [refreshingId, setRefreshingId] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // Load filters on mount
  useEffect(() => {
    const loadFilters = async () => {
      try {
        const [brandsData, yearsData, monthsData] = await Promise.all([
          vehiclePricesApi.getBrands(),
          vehiclePricesApi.getYears(),
          vehiclePricesApi.getReferenceMonths(),
        ])
        setBrands(brandsData)
        setYears(yearsData)
        setReferenceMonths(monthsData)
      } catch (err) {
        console.error('Erro ao carregar filtros:', err)
      }
    }
    loadFilters()
  }, [])

  // Load data
  const loadData = async () => {
    setLoading(true)
    setError(null)

    try {
      const result = await vehiclePricesApi.list({
        page,
        page_size: pageSize,
        brand_name: selectedBrand || undefined,
        year_model: selectedYear ? parseInt(selectedYear) : undefined,
        reference_month: selectedMonth || undefined,
        status: selectedStatus ? selectedStatus as 'Vigente' | 'Expirada' : undefined,
        codigo_fipe: searchFipe || undefined,
        model_name: searchModel || undefined,
        sort_by: 'updated_at',
        sort_order: 'desc',
      })
      setData(result)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar dados')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [page, selectedBrand, selectedYear, selectedMonth, selectedStatus])

  // Handle search (with debounce)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (page === 1) {
        loadData()
      } else {
        setPage(1)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [searchFipe, searchModel])

  // Clear filters
  const handleClearFilters = () => {
    setSelectedBrand('')
    setSelectedYear('')
    setSelectedMonth('')
    setSelectedStatus('')
    setSearchFipe('')
    setSearchModel('')
    setPage(1)
  }

  // Refresh single vehicle price
  const handleRefresh = async (vehicle: VehiclePrice) => {
    setRefreshingId(vehicle.id)
    setMessage(null)

    try {
      const result = await vehiclePricesApi.refresh(vehicle.id)

      if (result.success) {
        setMessage({
          type: 'success',
          text: `Preco atualizado! ${vehicle.vehicle_name}: R$ ${result.old_price?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })} -> R$ ${result.new_price?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`,
        })
        loadData()
      } else {
        setMessage({
          type: 'error',
          text: result.message,
        })
      }
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.message || 'Erro ao atualizar preco',
      })
    } finally {
      setRefreshingId(null)
      setTimeout(() => setMessage(null), 5000)
    }
  }

  // Format currency
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(value)
  }

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('pt-BR')
  }

  // Fuel type badge color
  const getFuelBadgeColor = (fuelType: string) => {
    const colors: { [key: string]: string } = {
      'Gasolina': 'bg-yellow-100 text-yellow-800',
      'Flex': 'bg-green-100 text-green-800',
      'Diesel': 'bg-gray-100 text-gray-800',
      'Alcool': 'bg-blue-100 text-blue-800',
    }
    return colors[fuelType] || 'bg-gray-100 text-gray-800'
  }

  // Status badge color
  const getStatusBadgeColor = (status: string) => {
    return status === 'Vigente'
      ? 'bg-green-100 text-green-800'
      : 'bg-red-100 text-red-800'
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Banco de Precos de Veiculos</h1>
        <p className="text-gray-600 mt-1">
          Historico de cotacoes FIPE realizadas pelo sistema
        </p>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`mb-4 p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          {/* Brand Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Marca
            </label>
            <select
              value={selectedBrand}
              onChange={(e) => { setSelectedBrand(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Todas</option>
              {brands.map((brand) => (
                <option key={brand} value={brand}>
                  {brand}
                </option>
              ))}
            </select>
          </div>

          {/* Year Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Ano Modelo
            </label>
            <select
              value={selectedYear}
              onChange={(e) => { setSelectedYear(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Todos</option>
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>

          {/* Reference Month Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Mes Referencia
            </label>
            <select
              value={selectedMonth}
              onChange={(e) => { setSelectedMonth(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Todos</option>
              {referenceMonths.map((month) => (
                <option key={month} value={month}>
                  {month}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={selectedStatus}
              onChange={(e) => { setSelectedStatus(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Todos</option>
              <option value="Vigente">Vigente</option>
              <option value="Expirada">Expirada</option>
            </select>
          </div>

          {/* FIPE Code Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Codigo FIPE
            </label>
            <input
              type="text"
              value={searchFipe}
              onChange={(e) => setSearchFipe(e.target.value)}
              placeholder="Ex: 001267-9"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>

          {/* Model Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Modelo
            </label>
            <input
              type="text"
              value={searchModel}
              onChange={(e) => setSearchModel(e.target.value)}
              placeholder="Buscar modelo..."
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Clear Filters */}
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleClearFilters}
            className="text-sm text-gray-600 hover:text-gray-800"
          >
            Limpar filtros
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            Carregando...
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-500">
            {error}
          </div>
        ) : data && data.items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Veiculo
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Codigo FIPE
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ano
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Combustivel
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Preco FIPE
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Referencia
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Atualizado em
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Acoes
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data.items.map((vehicle) => (
                    <tr key={vehicle.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <div className="text-sm font-medium text-gray-900">
                          {vehicle.brand_name}
                        </div>
                        <div className="text-sm text-gray-500">
                          {vehicle.model_name}
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900 font-mono">
                        {vehicle.codigo_fipe}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900">
                        {vehicle.year_model}
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getFuelBadgeColor(
                            vehicle.fuel_type
                          )}`}
                        >
                          {vehicle.fuel_type}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900 text-right font-semibold">
                        {formatCurrency(vehicle.price_value)}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-500">
                        {vehicle.reference_month}
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadgeColor(
                            vehicle.status
                          )}`}
                        >
                          {vehicle.status}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-500">
                        {formatDate(vehicle.updated_at)}
                      </td>
                      <td className="px-4 py-4 text-center">
                        <button
                          onClick={() => handleRefresh(vehicle)}
                          disabled={refreshingId === vehicle.id}
                          className={`inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md ${
                            refreshingId === vehicle.id
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : 'text-blue-700 bg-blue-100 hover:bg-blue-200'
                          }`}
                        >
                          {refreshingId === vehicle.id ? (
                            <>
                              <svg
                                className="animate-spin -ml-1 mr-2 h-4 w-4"
                                fill="none"
                                viewBox="0 0 24 24"
                              >
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                />
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                />
                              </svg>
                              Atualizando...
                            </>
                          ) : (
                            <>
                              <svg
                                className="-ml-0.5 mr-1.5 h-4 w-4"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                                />
                              </svg>
                              Atualizar
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data.total_pages > 1 && (
              <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200">
                <div className="flex-1 flex justify-between sm:hidden">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                    disabled={page === data.total_pages}
                    className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    Proximo
                  </button>
                </div>
                <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm text-gray-700">
                      Mostrando{' '}
                      <span className="font-medium">
                        {(page - 1) * pageSize + 1}
                      </span>{' '}
                      a{' '}
                      <span className="font-medium">
                        {Math.min(page * pageSize, data.total)}
                      </span>{' '}
                      de <span className="font-medium">{data.total}</span> veiculos
                    </p>
                  </div>
                  <div>
                    <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <span className="sr-only">Anterior</span>
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                      <span className="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">
                        Pagina {page} de {data.total_pages}
                      </span>
                      <button
                        onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                        disabled={page === data.total_pages}
                        className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <span className="sr-only">Proximo</span>
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                    </nav>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="p-8 text-center text-gray-500">
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <p className="text-lg font-medium">Nenhum veiculo encontrado</p>
            <p className="text-sm mt-1">
              O banco de precos sera populado automaticamente conforme cotacoes de veiculos forem realizadas.
            </p>
          </div>
        )}
      </div>

      {/* Info Card */}
      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">
              Sobre o Banco de Precos de Veiculos
            </h3>
            <div className="mt-2 text-sm text-blue-700">
              <ul className="list-disc pl-5 space-y-1">
                <li>Este banco armazena todas as cotacoes FIPE realizadas pelo sistema</li>
                <li>Use o botao "Atualizar" para obter o preco mais recente de um veiculo</li>
                <li>A referencia indica o mes da tabela FIPE utilizado na cotacao</li>
                <li>Veiculos cotados em meses anteriores podem ter precos desatualizados</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
