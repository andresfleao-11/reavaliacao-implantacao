'use client'

import { useState, useEffect } from 'react'
import { vehiclePricesApi, VehiclePrice, VehiclePriceListResponse, API_URL } from '@/lib/api'

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
  const [selectedScreenshot, setSelectedScreenshot] = useState<string>('')  // '', 'com', 'sem'
  const [searchFipe, setSearchFipe] = useState<string>('')
  const [searchModel, setSearchModel] = useState<string>('')

  // Screenshot preview modal
  const [previewVehicle, setPreviewVehicle] = useState<VehiclePrice | null>(null)
  const [retryingScreenshotId, setRetryingScreenshotId] = useState<number | null>(null)

  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize] = useState(15)

  // Actions state
  const [refreshingId, setRefreshingId] = useState<number | null>(null)
  const [exporting, setExporting] = useState(false)
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
        has_screenshot: selectedScreenshot === 'com' ? true : selectedScreenshot === 'sem' ? false : undefined,
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
  }, [page, selectedBrand, selectedYear, selectedMonth, selectedStatus, selectedScreenshot])

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
    setSelectedScreenshot('')
    setSearchFipe('')
    setSearchModel('')
    setPage(1)
  }

  // Retry screenshot
  const handleRetryScreenshot = async (vehicle: VehiclePrice) => {
    setRetryingScreenshotId(vehicle.id)
    setMessage(null)

    try {
      const result = await vehiclePricesApi.retryScreenshot(vehicle.id)

      if (result.success) {
        setMessage({
          type: 'success',
          text: `Screenshot capturado com sucesso para ${vehicle.vehicle_name}`,
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
        text: err.message || 'Erro ao capturar screenshot',
      })
    } finally {
      setRetryingScreenshotId(null)
      setTimeout(() => setMessage(null), 5000)
    }
  }

  // Export CSV
  const handleExportCSV = async () => {
    setExporting(true)
    try {
      await vehiclePricesApi.exportCSV({
        brand_name: selectedBrand || undefined,
        year_model: selectedYear ? parseInt(selectedYear) : undefined,
        reference_month: selectedMonth || undefined,
        status: selectedStatus ? selectedStatus as 'Vigente' | 'Expirada' | 'Pendente' : undefined,
      })
      setMessage({ type: 'success', text: 'CSV exportado com sucesso!' })
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Erro ao exportar CSV' })
    } finally {
      setExporting(false)
      setTimeout(() => setMessage(null), 3000)
    }
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
    switch (status) {
      case 'Vigente':
        return 'bg-green-100 text-green-800'
      case 'Pendente':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-red-100 text-red-800'
    }
  }

  return (
    <div className="p-0">
      <div className="mb-4 sm:mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">Banco de Preços de Veículos</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          Histórico de cotações FIPE realizadas pelo sistema
        </p>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`mb-4 p-3 sm:p-4 rounded-lg text-sm ${
            message.type === 'success'
              ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3 sm:p-4 mb-4 sm:mb-6">
        <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-4">
          {/* Brand Filter */}
          <div>
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Marca
            </label>
            <select
              value={selectedBrand}
              onChange={(e) => { setSelectedBrand(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Ano
            </label>
            <select
              value={selectedYear}
              onChange={(e) => { setSelectedYear(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Mês Ref.
            </label>
            <select
              value={selectedMonth}
              onChange={(e) => { setSelectedMonth(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Status
            </label>
            <select
              value={selectedStatus}
              onChange={(e) => { setSelectedStatus(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              <option value="">Todos</option>
              <option value="Vigente">Vigente</option>
              <option value="Expirada">Expirada</option>
              <option value="Pendente">Pendente</option>
            </select>
          </div>

          {/* Screenshot Filter */}
          <div>
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Print
            </label>
            <select
              value={selectedScreenshot}
              onChange={(e) => { setSelectedScreenshot(e.target.value); setPage(1) }}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              <option value="">Todos</option>
              <option value="com">Com Print</option>
              <option value="sem">Sem Print</option>
            </select>
          </div>

          {/* FIPE Code Search */}
          <div>
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Cód. FIPE
            </label>
            <input
              type="text"
              value={searchFipe}
              onChange={(e) => setSearchFipe(e.target.value)}
              placeholder="001267-9"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>

          {/* Model Search */}
          <div>
            <label className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Modelo
            </label>
            <input
              type="text"
              value={searchModel}
              onChange={(e) => setSearchModel(e.target.value)}
              placeholder="Buscar..."
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
        </div>

        {/* Actions: Clear Filters & Export CSV */}
        <div className="mt-3 sm:mt-4 flex justify-between items-center">
          <button
            onClick={handleExportCSV}
            disabled={exporting}
            className="inline-flex items-center px-3 py-1.5 border border-green-300 dark:border-green-700 text-xs sm:text-sm font-medium rounded-md text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-900/30 hover:bg-green-100 dark:hover:bg-green-900/50 disabled:opacity-50"
          >
            {exporting ? (
              <>
                <svg className="animate-spin h-4 w-4 mr-1.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Exportando...
              </>
            ) : (
              <>
                <svg className="h-4 w-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Exportar CSV
              </>
            )}
          </button>
          <button
            onClick={handleClearFilters}
            className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          >
            Limpar filtros
          </button>
        </div>
      </div>

      {/* Loading/Error States */}
      {loading ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 sm:p-8 text-center text-gray-500 dark:text-gray-400">
          <div className="animate-spin rounded-full h-6 w-6 sm:h-8 sm:w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <span className="text-sm">Carregando...</span>
        </div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 sm:p-8 text-center text-sm text-red-500 dark:text-red-400">
          {error}
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          {/* Desktop Table */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden hidden md:block">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Veículo
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      FIPE
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Ano
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider hidden lg:table-cell">
                      Comb.
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Preço
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Data Cotação
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Print
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {data.items.map((vehicle) => (
                    <tr key={vehicle.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <td className="px-4 py-4">
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[180px]">
                          {vehicle.brand_name}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[180px]">
                          {vehicle.model_name}
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900 dark:text-gray-100 font-mono">
                        {vehicle.codigo_fipe}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900 dark:text-gray-100">
                        {vehicle.year_model}
                      </td>
                      <td className="px-4 py-4 hidden lg:table-cell">
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-semibold rounded-full ${getFuelBadgeColor(
                            vehicle.fuel_type
                          )}`}
                        >
                          {vehicle.fuel_type}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900 dark:text-gray-100 text-right font-semibold whitespace-nowrap">
                        {formatCurrency(vehicle.price_value)}
                      </td>
                      <td className="px-4 py-4 text-center text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">
                        {formatDate(vehicle.updated_at)}
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-semibold rounded-full ${getStatusBadgeColor(
                            vehicle.status
                          )}`}
                        >
                          {vehicle.status}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-center">
                        {vehicle.has_screenshot ? (
                          <button
                            onClick={() => setPreviewVehicle(vehicle)}
                            className="hover:scale-110 transition-transform"
                            title="Clique para visualizar"
                          >
                            <svg
                              className="h-5 w-5 text-green-500 mx-auto cursor-pointer"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                              />
                            </svg>
                          </button>
                        ) : (
                          <button
                            onClick={() => handleRetryScreenshot(vehicle)}
                            disabled={retryingScreenshotId === vehicle.id}
                            className="hover:scale-110 transition-transform disabled:opacity-50"
                            title="Clique para capturar screenshot"
                          >
                            {retryingScreenshotId === vehicle.id ? (
                              <svg className="animate-spin h-5 w-5 text-yellow-500 mx-auto" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                              </svg>
                            ) : (
                              <svg
                                className="h-5 w-5 text-yellow-500 mx-auto cursor-pointer"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                                />
                              </svg>
                            )}
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-4 text-center">
                        <button
                          onClick={() => handleRefresh(vehicle)}
                          disabled={refreshingId === vehicle.id}
                          className={`inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md ${
                            refreshingId === vehicle.id
                              ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                              : 'text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                          }`}
                        >
                          {refreshingId === vehicle.id ? (
                            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                          ) : (
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-2">
            {data.items.map((vehicle) => (
              <div key={vehicle.id} className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
                {/* Header: Marca e Status */}
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {vehicle.brand_name}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {vehicle.model_name}
                    </div>
                  </div>
                  <span
                    className={`ml-2 flex-shrink-0 inline-flex px-1.5 py-0.5 text-[10px] font-semibold rounded-full ${getStatusBadgeColor(
                      vehicle.status
                    )}`}
                  >
                    {vehicle.status}
                  </span>
                </div>

                {/* Info Row: FIPE, Ano, Combustível, Data */}
                <div className="flex items-center flex-wrap gap-2 text-xs text-gray-600 dark:text-gray-400 mb-2">
                  <span className="font-mono">{vehicle.codigo_fipe}</span>
                  <span>•</span>
                  <span>{vehicle.year_model}</span>
                  <span>•</span>
                  <span
                    className={`inline-flex px-1.5 py-0.5 text-[10px] font-semibold rounded-full ${getFuelBadgeColor(
                      vehicle.fuel_type
                    )}`}
                  >
                    {vehicle.fuel_type}
                  </span>
                  <span>•</span>
                  <span className="text-gray-500">{formatDate(vehicle.updated_at)}</span>
                </div>

                {/* Footer: Preço e Ações */}
                <div className="flex justify-between items-center pt-2 border-t border-gray-100 dark:border-gray-700">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-primary-600 dark:text-primary-400">
                      {formatCurrency(vehicle.price_value)}
                    </span>
                    {vehicle.has_screenshot ? (
                      <button onClick={() => setPreviewVehicle(vehicle)} className="hover:scale-110 transition-transform">
                        <svg className="h-4 w-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleRetryScreenshot(vehicle)}
                        disabled={retryingScreenshotId === vehicle.id}
                        className="hover:scale-110 transition-transform disabled:opacity-50"
                      >
                        {retryingScreenshotId === vehicle.id ? (
                          <svg className="animate-spin h-4 w-4 text-yellow-500" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          <svg className="h-4 w-4 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => handleRefresh(vehicle)}
                    disabled={refreshingId === vehicle.id}
                    className={`inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded-md ${
                      refreshingId === vehicle.id
                        ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                        : 'text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                    }`}
                  >
                    {refreshingId === vehicle.id ? (
                      <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <>
                        <svg className="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Atualizar
                      </>
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow mt-4 px-3 sm:px-4 py-2 sm:py-3 flex flex-col sm:flex-row items-center justify-between gap-2">
              <div className="text-xs sm:text-sm text-gray-700 dark:text-gray-300">
                {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, data.total)} de {data.total}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-2 sm:px-3 py-1 border border-gray-300 dark:border-gray-600 text-xs sm:text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  Anterior
                </button>
                <span className="text-xs sm:text-sm text-gray-700 dark:text-gray-300">
                  {page}/{data.total_pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page === data.total_pages}
                  className="px-2 sm:px-3 py-1 border border-gray-300 dark:border-gray-600 text-xs sm:text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  Próximo
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 sm:p-8 text-center text-gray-500 dark:text-gray-400">
          <svg
            className="mx-auto h-10 w-10 sm:h-12 sm:w-12 text-gray-400 dark:text-gray-500 mb-4"
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
          <p className="text-sm sm:text-base font-medium">Nenhum veículo encontrado</p>
          <p className="text-xs sm:text-sm mt-1">
            O banco de preços será populado automaticamente conforme cotações de veículos forem realizadas.
          </p>
        </div>
      )}

      {/* Info Card */}
      <div className="mt-4 sm:mt-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 sm:p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-4 w-4 sm:h-5 sm:w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-2 sm:ml-3">
            <h3 className="text-xs sm:text-sm font-medium text-blue-800 dark:text-blue-300">
              Sobre o Banco de Preços de Veículos
            </h3>
            <div className="mt-1 sm:mt-2 text-xs sm:text-sm text-blue-700 dark:text-blue-400">
              <ul className="list-disc pl-4 sm:pl-5 space-y-0.5 sm:space-y-1">
                <li>Este banco armazena todas as cotações FIPE realizadas pelo sistema</li>
                <li>Use o botão "Atualizar" para obter o preço mais recente de um veículo</li>
                <li>Clique no icone de camera verde para visualizar o screenshot FIPE</li>
                <li>Clique no icone amarelo para capturar o screenshot pendente</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Screenshot Preview Modal */}
      {previewVehicle && (
        <div
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4"
          onClick={() => setPreviewVehicle(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  Screenshot FIPE
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {previewVehicle.brand_name} {previewVehicle.model_name} - {previewVehicle.year_model}
                </p>
              </div>
              <button
                onClick={() => setPreviewVehicle(null)}
                className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Image */}
            <div className="p-4">
              <div className="bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden">
                <img
                  src={vehiclePricesApi.getScreenshotUrl(previewVehicle.id)}
                  alt={`Screenshot FIPE ${previewVehicle.codigo_fipe}`}
                  className="w-full h-auto"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect fill="%23f3f4f6" width="400" height="300"/><text x="50%" y="50%" text-anchor="middle" fill="%239ca3af">Erro ao carregar imagem</text></svg>'
                  }}
                />
              </div>

              {/* Info */}
              <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-gray-500 dark:text-gray-400">Codigo FIPE</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">{previewVehicle.codigo_fipe}</p>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400">Preco</p>
                  <p className="font-semibold text-green-600 dark:text-green-400">{formatCurrency(previewVehicle.price_value)}</p>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400">Combustivel</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">{previewVehicle.fuel_type}</p>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400">Referencia</p>
                  <p className="font-semibold text-gray-900 dark:text-gray-100">{previewVehicle.reference_month}</p>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="border-t border-gray-200 dark:border-gray-700 px-4 py-3 flex justify-end gap-2">
              <a
                href={vehiclePricesApi.getScreenshotUrl(previewVehicle.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700"
              >
                Abrir em nova aba
              </a>
              <button
                onClick={() => setPreviewVehicle(null)}
                className="px-4 py-2 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
