'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { settingsApi, Parameters, SerpApiLocationOption, BlockedDomain } from '@/lib/api'

export default function ParametrosPage() {
  const { data, error, mutate } = useSWR('/settings/parameters', settingsApi.getParameters)

  const [locations, setLocations] = useState<SerpApiLocationOption[]>([])
  const [formData, setFormData] = useState<Partial<Parameters>>({})
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  // Blocked domains state - using manual state instead of SWR
  const [blockedDomains, setBlockedDomains] = useState<BlockedDomain[] | null>(null)
  const [domainsError, setDomainsError] = useState<Error | null>(null)
  const [loadingDomains, setLoadingDomains] = useState(true)

  const [showDomainModal, setShowDomainModal] = useState(false)
  const [editingDomain, setEditingDomain] = useState<BlockedDomain | null>(null)
  const [domainForm, setDomainForm] = useState({ domain: '', display_name: '', reason: '' })
  const [generatingName, setGeneratingName] = useState(false)
  const [savingDomain, setSavingDomain] = useState(false)
  const [domainMessage, setDomainMessage] = useState('')

  // Load blocked domains manually
  const loadBlockedDomains = async () => {
    console.log('loadBlockedDomains called')
    try {
      setLoadingDomains(true)
      console.log('Fetching blocked domains from API...')
      const domains = await settingsApi.getBlockedDomains()
      console.log('Loaded blocked domains:', domains)
      setBlockedDomains(domains)
      setDomainsError(null)
    } catch (err: any) {
      console.error('Error loading blocked domains:', err)
      setDomainsError(err)
    } finally {
      setLoadingDomains(false)
    }
  }

  useEffect(() => {
    console.log('Component mounted, loading data...')

    // Load locations
    settingsApi.getSerpApiLocations()
      .then(setLocations)
      .catch(err => console.error('Error loading locations:', err))

    // Load blocked domains
    loadBlockedDomains()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')

    try {
      await settingsApi.updateParameters(formData)
      setMessage('Parâmetros salvos com sucesso!')
      mutate()
      setFormData({})
    } catch (err) {
      setMessage('Erro ao salvar parâmetros')
    } finally {
      setSaving(false)
    }
  }

  const handleGenerateName = async () => {
    if (!domainForm.domain) {
      setDomainMessage('Digite um domínio primeiro')
      return
    }

    setGeneratingName(true)
    setDomainMessage('')

    try {
      const result = await settingsApi.generateDomainName(domainForm.domain)
      setDomainForm({ ...domainForm, display_name: result.display_name })
      setDomainMessage('Nome gerado com sucesso!')
    } catch (err) {
      setDomainMessage('Erro ao gerar nome')
    } finally {
      setGeneratingName(false)
    }
  }

  const handleOpenDomainModal = (domain?: BlockedDomain) => {
    if (domain) {
      setEditingDomain(domain)
      setDomainForm({
        domain: domain.domain,
        display_name: domain.display_name || '',
        reason: domain.reason || ''
      })
    } else {
      setEditingDomain(null)
      setDomainForm({ domain: '', display_name: '', reason: '' })
    }
    setDomainMessage('')
    setShowDomainModal(true)
  }

  const handleCloseDomainModal = () => {
    setShowDomainModal(false)
    setEditingDomain(null)
    setDomainForm({ domain: '', display_name: '', reason: '' })
    setDomainMessage('')
  }

  const handleSaveDomain = async () => {
    setSavingDomain(true)
    setDomainMessage('')

    try {
      if (editingDomain) {
        await settingsApi.updateBlockedDomain(editingDomain.id, domainForm)
        setDomainMessage('Domínio atualizado com sucesso!')
      } else {
        await settingsApi.createBlockedDomain(domainForm)
        setDomainMessage('Domínio adicionado com sucesso!')
      }

      await loadBlockedDomains()
      setTimeout(() => {
        handleCloseDomainModal()
      }, 1500)
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || 'Erro ao salvar domínio'
      setDomainMessage(errorMsg)
    } finally {
      setSavingDomain(false)
    }
  }

  const handleDeleteDomain = async (id: number) => {
    if (!confirm('Deseja realmente remover este domínio da lista de bloqueados?')) return

    try {
      await settingsApi.deleteBlockedDomain(id)
      await loadBlockedDomains()
      setMessage('Domínio removido com sucesso!')
      setTimeout(() => setMessage(''), 3000)
    } catch (err) {
      setMessage('Erro ao remover domínio')
    }
  }

  if (!data) return <div className="card text-gray-600 dark:text-gray-400">Carregando...</div>

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-8">Parâmetros do Sistema</h1>

      {message && (
        <div className={`mb-6 px-4 py-3 rounded-lg ${message.includes('sucesso') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}`}>
          {message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="card space-y-6 mb-8">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Número de Cotações por Pesquisa
          </label>
          <input
            type="number"
            defaultValue={data.numero_cotacoes_por_pesquisa}
            onChange={(e) => setFormData({...formData, numero_cotacoes_por_pesquisa: parseInt(e.target.value)})}
            className="input-field w-full"
            min="1"
            max="10"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Variação Máxima (%)
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Fórmula: (MAX / MIN - 1) × 100</p>
          <input
            type="number"
            step="0.1"
            defaultValue={data.variacao_maxima_percent}
            onChange={(e) => setFormData({...formData, variacao_maxima_percent: parseFloat(e.target.value)})}
            className="input-field w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Pesquisador Padrão
          </label>
          <input
            type="text"
            defaultValue={data.pesquisador_padrao}
            onChange={(e) => setFormData({...formData, pesquisador_padrao: e.target.value})}
            className="input-field w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Local Padrão
          </label>
          <input
            type="text"
            defaultValue={data.local_padrao}
            onChange={(e) => setFormData({...formData, local_padrao: e.target.value})}
            className="input-field w-full"
          />
        </div>

        <div className="border-t border-gray-200 dark:border-gray-700 pt-6 mt-6">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Banco de Preços de Veículos</h3>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Vigência de Cotação (meses)
            </label>
            <input
              type="number"
              defaultValue={data.vigencia_cotacao_veiculos || 6}
              onChange={(e) => setFormData({...formData, vigencia_cotacao_veiculos: parseInt(e.target.value)})}
              className="input-field w-full"
              min="1"
              max="24"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Define por quantos meses uma cotação de veículo permanece vigente. Cotações com idade superior serão consideradas expiradas e atualizadas na próxima consulta.
            </p>
          </div>
        </div>

        <div className="border-t border-gray-200 dark:border-gray-700 pt-6 mt-6">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Parâmetros de Busca (SerpAPI)</h3>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Localização da Busca
            </label>
            <select
              defaultValue={data.serpapi_location}
              onChange={(e) => setFormData({...formData, serpapi_location: e.target.value})}
              className="input-field w-full"
            >
              {locations.map((loc) => (
                <option key={loc.value} value={loc.value}>
                  {loc.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Define a região geográfica para busca de preços no Google Shopping
            </p>
          </div>
        </div>

        <div className="flex justify-end">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      </form>

      {/* Blocked Domains Section */}
      <div className="card">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Domínios Bloqueados</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Sites bloqueados para pesquisa de cotações</p>
          </div>
          <button
            onClick={() => handleOpenDomainModal()}
            className="btn-primary"
          >
            Adicionar Domínio
          </button>
        </div>

        {domainsError ? (
          <div className="text-center py-8 text-red-600 dark:text-red-400">
            Erro ao carregar domínios bloqueados: {domainsError.message}
          </div>
        ) : !blockedDomains ? (
          <div className="text-center py-4 text-gray-500 dark:text-gray-400">Carregando...</div>
        ) : blockedDomains.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">Nenhum domínio bloqueado</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Domínio
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Nome
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Motivo
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {blockedDomains.map((domain) => (
                  <tr key={domain.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">{domain.domain}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{domain.display_name || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{domain.reason || '-'}</td>
                    <td className="px-4 py-3 text-sm text-right space-x-2">
                      <button
                        onClick={() => handleOpenDomainModal(domain)}
                        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDeleteDomain(domain.id)}
                        className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                      >
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Domain Modal */}
      {showDomainModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              {editingDomain ? 'Editar Domínio Bloqueado' : 'Adicionar Domínio Bloqueado'}
            </h3>

            {domainMessage && (
              <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${domainMessage.includes('sucesso') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}`}>
                {domainMessage}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Domínio
                </label>
                <input
                  type="text"
                  value={domainForm.domain}
                  onChange={(e) => setDomainForm({ ...domainForm, domain: e.target.value })}
                  className="input-field w-full"
                  placeholder="exemplo.com.br"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Nome de Exibição
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={domainForm.display_name}
                    onChange={(e) => setDomainForm({ ...domainForm, display_name: e.target.value })}
                    className="input-field flex-1"
                    placeholder="Nome do site"
                  />
                  <button
                    type="button"
                    onClick={handleGenerateName}
                    disabled={generatingName || !domainForm.domain}
                    className="btn-primary px-4 whitespace-nowrap"
                  >
                    {generatingName ? 'Gerando...' : 'Gerar com IA'}
                  </button>
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Use o botão para gerar automaticamente o nome usando IA
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Motivo do Bloqueio
                </label>
                <textarea
                  value={domainForm.reason}
                  onChange={(e) => setDomainForm({ ...domainForm, reason: e.target.value })}
                  className="input-field w-full"
                  rows={3}
                  placeholder="Ex: Proteção anti-bot forte"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={handleCloseDomainModal}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                disabled={savingDomain}
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveDomain}
                className="btn-primary"
                disabled={savingDomain || !domainForm.domain}
              >
                {savingDomain ? 'Salvando...' : editingDomain ? 'Atualizar' : 'Adicionar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
