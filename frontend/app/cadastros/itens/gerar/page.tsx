'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import AdminRoute from '@/components/AdminRoute'

interface Client {
  id: number
  nome: string
  nome_curto: string | null
}

interface MaterialCharacteristic {
  id: number
  nome: string
  descricao: string | null
  tipo_dado: string
  opcoes_json: string[] | null
}

interface Material {
  id: number
  nome: string
  codigo: string | null
  client_id: number | null
  caracteristicas: MaterialCharacteristic[]
}

interface CharacteristicValue {
  nome: string
  valor: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function GerarItensPage() {
  const router = useRouter()
  const [clients, setClients] = useState<Client[]>([])
  const [allMaterials, setAllMaterials] = useState<Material[]>([])
  const [filteredMaterials, setFilteredMaterials] = useState<Material[]>([])

  const [selectedClientId, setSelectedClientId] = useState<number | null>(null)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null)

  // Características que serão usadas (permitir exclusão)
  const [enabledCharacteristics, setEnabledCharacteristics] = useState<string[]>([])

  // Lista de conjuntos de características
  const [itemsList, setItemsList] = useState<CharacteristicValue[][]>([])
  const [currentSet, setCurrentSet] = useState<CharacteristicValue[]>([])

  const [quantidade, setQuantidade] = useState(1)
  const [codigoInicial, setCodigoInicial] = useState('')

  const [result, setResult] = useState<{created: number, skipped: number, errors: string[]} | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchClients()
    fetchMaterials()
  }, [])

  useEffect(() => {
    // Filtrar materiais por cliente
    if (selectedClientId) {
      setFilteredMaterials(
        allMaterials.filter(m => m.client_id === selectedClientId)
      )
    } else {
      setFilteredMaterials(allMaterials)
    }
  }, [selectedClientId, allMaterials])

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_URL}/api/clients/options/list`)
      const data = await res.json()
      setClients(data)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchMaterials = async () => {
    try {
      const res = await fetch(`${API_URL}/api/materials?per_page=1000`)
      const data = await res.json()
      setAllMaterials(data.items || [])
      setFilteredMaterials(data.items || [])
    } catch (err) {
      console.error(err)
    }
  }

  const handleMaterialSelect = async (materialId: number) => {
    setSelectedMaterialId(materialId)
    try {
      const res = await fetch(`${API_URL}/api/materials/${materialId}`)
      const material = await res.json()
      setSelectedMaterial(material)

      // Inicializar todas as características como habilitadas
      const charNames = material.caracteristicas.map((c: MaterialCharacteristic) => c.nome)
      setEnabledCharacteristics(charNames)

      // Inicializar conjunto atual
      const initialSet = material.caracteristicas.map((c: MaterialCharacteristic) => ({
        nome: c.nome,
        valor: ''
      }))
      setCurrentSet(initialSet)
      setItemsList([])
    } catch (err) {
      console.error(err)
    }
  }

  const toggleCharacteristic = (charName: string) => {
    if (enabledCharacteristics.includes(charName)) {
      setEnabledCharacteristics(enabledCharacteristics.filter(n => n !== charName))
    } else {
      setEnabledCharacteristics([...enabledCharacteristics, charName])
    }
  }

  const updateCharValue = (index: number, value: string) => {
    const updated = [...currentSet]
    updated[index].valor = value
    setCurrentSet(updated)
  }

  const addCurrentSetToList = () => {
    // Validar se características habilitadas estão preenchidas
    const enabledSet = currentSet.filter(c => enabledCharacteristics.includes(c.nome))
    const allFilled = enabledSet.every(c => c.valor.trim() !== '')

    if (!allFilled) {
      alert('Preencha todas as características habilitadas antes de adicionar')
      return
    }

    setItemsList([...itemsList, enabledSet])

    // Resetar conjunto atual
    const newSet = selectedMaterial!.caracteristicas.map((c: MaterialCharacteristic) => ({
      nome: c.nome,
      valor: ''
    }))
    setCurrentSet(newSet)
  }

  const removeItem = (index: number) => {
    setItemsList(itemsList.filter((_, i) => i !== index))
  }

  const handleGenerate = async () => {
    if (!selectedClientId || !selectedMaterialId) {
      alert('Selecione cliente e material')
      return
    }

    if (itemsList.length === 0) {
      alert('Adicione pelo menos um conjunto de características')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/materials/items/bulk-create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: selectedClientId,
          material_id: selectedMaterialId,
          items: itemsList,
          codigo_inicial: codigoInicial || null
        })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Erro ao gerar itens')
      }

      const data = await res.json()
      setResult(data)

      if (data.created > 0) {
        alert(`${data.created} itens criados com sucesso!`)
        // Limpar formulário
        setItemsList([])
        setSelectedMaterialId(null)
        setSelectedMaterial(null)
      }
    } catch (err: any) {
      alert('Erro ao gerar itens: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AdminRoute>
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Gerar Itens em Lote</h1>
        <button
          onClick={() => router.push('/cadastros/itens')}
          className="px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          ← Voltar
        </button>
      </div>

      {/* Passo 1: Selecionar Cliente e Material */}
      <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">1. Selecione o Cliente e Material</h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Cliente *</label>
            <select
              value={selectedClientId || ''}
              onChange={(e) => {
                const clientId = e.target.value ? Number(e.target.value) : null
                setSelectedClientId(clientId)
                setSelectedMaterialId(null)
                setSelectedMaterial(null)
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Selecione um cliente...</option>
              {clients.map(c => (
                <option key={c.id} value={c.id}>{c.nome_curto || c.nome}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Material *</label>
            <select
              value={selectedMaterialId || ''}
              onChange={(e) => e.target.value && handleMaterialSelect(Number(e.target.value))}
              disabled={!selectedClientId}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100"
            >
              <option value="">Selecione um material...</option>
              {filteredMaterials.map(m => (
                <option key={m.id} value={m.id}>
                  {m.codigo ? `[${m.codigo}] ` : ''}{m.nome}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Passo 2: Selecionar Características */}
      {selectedMaterial && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">2. Selecione as Características a Utilizar</h2>
          <p className="text-sm text-gray-600 mb-4">
            Desmarque as características que não deseja incluir nos itens
          </p>

          <div className="space-y-2">
            {selectedMaterial.caracteristicas.map((char) => (
              <label key={char.id} className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enabledCharacteristics.includes(char.nome)}
                  onChange={() => toggleCharacteristic(char.nome)}
                  className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                />
                <span className="text-sm font-medium">{char.nome}</span>
                {char.descricao && (
                  <span className="text-xs text-gray-500">({char.descricao})</span>
                )}
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Passo 3: Adicionar Itens */}
      {selectedMaterial && enabledCharacteristics.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">3. Defina os Valores das Características</h2>

          {currentSet
            .filter(char => enabledCharacteristics.includes(char.nome))
            .map((char, idx) => {
              const charDef = selectedMaterial.caracteristicas.find(c => c.nome === char.nome)
              const actualIndex = currentSet.findIndex(c => c.nome === char.nome)

              return (
                <div key={char.nome} className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {char.nome}
                    {charDef?.descricao && (
                      <span className="text-gray-400 font-normal ml-1">
                        ({charDef.descricao})
                      </span>
                    )}
                  </label>

                  {charDef?.tipo_dado === 'lista' && charDef.opcoes_json ? (
                    <select
                      value={char.valor}
                      onChange={(e) => updateCharValue(actualIndex, e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="">Selecione...</option>
                      {charDef.opcoes_json.map((opcao, i) => (
                        <option key={i} value={opcao}>{opcao}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={char.valor}
                      onChange={(e) => updateCharValue(actualIndex, e.target.value)}
                      placeholder={`Informe ${char.nome.toLowerCase()}`}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                    />
                  )}
                </div>
              )
            })}

          <button
            onClick={addCurrentSetToList}
            className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            + Adicionar à Lista
          </button>
        </div>
      )}

      {/* Passo 4: Lista de Itens */}
      {itemsList.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            4. Itens a Gerar ({itemsList.length})
          </h2>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Código Inicial (opcional)
            </label>
            <input
              type="text"
              value={codigoInicial}
              onChange={(e) => setCodigoInicial(e.target.value)}
              placeholder="Ex: 001 (será gerado 001, 002, 003...)"
              className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Se não informado, será gerado sequencial automático
            </p>
          </div>

          <div className="space-y-2 mb-4">
            {itemsList.map((item, idx) => (
              <div key={idx} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div className="flex gap-4 flex-wrap">
                  {item.map((char, charIdx) => (
                    <span key={charIdx} className="text-sm">
                      <strong className="text-gray-700">{char.nome}:</strong>{' '}
                      <span className="text-gray-900">{char.valor}</span>
                    </span>
                  ))}
                </div>
                <button
                  onClick={() => removeItem(idx)}
                  className="text-red-600 hover:text-red-800 ml-4"
                >
                  Remover
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading}
            className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors font-medium"
          >
            {loading ? 'Gerando...' : `Gerar ${itemsList.length} Itens`}
          </button>
        </div>
      )}

      {/* Resultado */}
      {result && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">Resultado</h2>
          <div className="space-y-2">
            <p className="text-green-600 font-medium">✓ {result.created} itens criados</p>
            {result.skipped > 0 && (
              <p className="text-yellow-600">⊘ {result.skipped} duplicados ignorados</p>
            )}
            {result.errors && result.errors.length > 0 && (
              <div>
                <p className="text-red-600 font-medium">✗ {result.errors.length} erros:</p>
                <ul className="ml-4 text-sm text-red-600 mt-2">
                  {result.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <button
            onClick={() => router.push('/cadastros/itens')}
            className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Ver Lista de Itens
          </button>
        </div>
      )}
    </div>
    </AdminRoute>
  )
}
