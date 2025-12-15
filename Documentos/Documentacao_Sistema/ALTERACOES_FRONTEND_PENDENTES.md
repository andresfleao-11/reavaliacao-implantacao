# Alterações Pendentes no Frontend

## Status Atual
✅ Backend 100% implementado e funcional
⚠️ Frontend precisa ser atualizado para usar as novas funcionalidades

## 1. Formulário de Materiais (`frontend/app/cadastros/materiais/page.tsx`)

### Alterações necessárias:

#### 1.1 Adicionar campo Cliente
```typescript
// Já adicionado ao state, falta incluir no formulário:
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Cliente
  </label>
  <select
    value={materialForm.client_id || ''}
    onChange={(e) => setMaterialForm({
      ...materialForm,
      client_id: e.target.value ? Number(e.target.value) : null
    })}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
  >
    <option value="">Selecione um cliente...</option>
    {clients.map((c) => (
      <option key={c.id} value={c.id}>
        {c.nome_curto || c.nome}
      </option>
    ))}
  </select>
</div>
```

#### 1.2 Adicionar campo Código (9 dígitos)
```typescript
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Código (9 dígitos)
  </label>
  <input
    type="text"
    maxLength={9}
    pattern="[0-9]{9}"
    value={materialForm.codigo}
    onChange={(e) => {
      // Permitir apenas números
      const value = e.target.value.replace(/\D/g, '')
      setMaterialForm({ ...materialForm, codigo: value })
    }}
    placeholder="000000000"
    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
  />
</div>
```

#### 1.3 Atualizar funções open...Modal
Já foi feito parcialmente, precisa completar:

```typescript
const openNewMaterialModal = () => {
  setEditingMaterial(null)
  setMaterialForm({ nome: '', descricao: '', client_id: null, codigo: '' })
  setError('')
  setShowMaterialModal(true)
}

const openEditMaterialModal = (material: Material) => {
  setEditingMaterial(material)
  setMaterialForm({
    nome: material.nome,
    descricao: material.descricao || '',
    client_id: material.client_id,
    codigo: material.codigo || ''
  })
  setError('')
  setShowMaterialModal(true)
}
```

#### 1.4 Adicionar filtro por cliente na listagem
```typescript
// Já adicionado ao fetchMaterials, adicionar na UI:
<select
  value={filterClientId}
  onChange={(e) => { setFilterClientId(e.target.value); setPage(1); }}
  className="px-4 py-2 border border-gray-300 rounded-lg"
>
  <option value="">Todos os clientes</option>
  {clients.map((c) => (
    <option key={c.id} value={c.id}>
      {c.nome_curto || c.nome}
    </option>
  ))}
</select>
```

## 2. Formulário de Itens (`frontend/app/cadastros/itens/page.tsx`)

### Alterações necessárias:

#### 2.1 Adicionar interfaces
```typescript
interface Client {
  id: number
  nome: string
  nome_curto: string | null
}
```

#### 2.2 Atualizar interface Item
```typescript
interface Item {
  id: number
  client_id: number | null  // ADICIONAR
  material_id: number
  material_nome: string
  // ... resto dos campos
}
```

#### 2.3 Adicionar state para clientes
```typescript
const [clients, setClients] = useState<Client[]>([])
const [filterClientId, setFilterClientId] = useState('')
```

#### 2.4 Adicionar fetchClients
```typescript
const fetchClients = async () => {
  try {
    const res = await fetch(`${API_URL}/api/clients/options/list`)
    const data = await res.json()
    setClients(data)
  } catch (err) {
    console.error('Erro ao carregar clientes:', err)
  }
}

useEffect(() => {
  fetchClients()
}, [])
```

#### 2.5 Atualizar formData
```typescript
const emptyItem = {
  client_id: null as number | null,  // ADICIONAR
  material_id: 0,
  codigo: '',
  // ... resto
}
```

#### 2.6 Adicionar campo Cliente no formulário
```typescript
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Cliente
  </label>
  <select
    value={formData.client_id || ''}
    onChange={(e) => setFormData({
      ...formData,
      client_id: e.target.value ? Number(e.target.value) : null
    })}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
  >
    <option value="">Selecione um cliente...</option>
    {clients.map((c) => (
      <option key={c.id} value={c.id}>{c.nome_curto || c.nome}</option>
    ))}
  </select>
</div>
```

#### 2.7 Adicionar filtro por cliente
```typescript
<select
  value={filterClientId}
  onChange={(e) => { setFilterClientId(e.target.value); setPage(1); }}
  className="px-4 py-2 border border-gray-300 rounded-lg"
>
  <option value="">Todos os clientes</option>
  {clients.map((c) => (
    <option key={c.id} value={c.id}>{c.nome_curto || c.nome}</option>
  ))}
</select>
```

## 3. Nova Tela: Geração de Itens em Lote

### Criar: `frontend/app/cadastros/itens/gerar/page.tsx`

```typescript
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

interface Client {
  id: number
  nome: string
  nome_curto: string | null
}

interface Material {
  id: number
  nome: string
  codigo: string | null
  caracteristicas: Characteristic[]
}

interface Characteristic {
  id: number
  nome: string
  tipo_dado: string
  opcoes: string[] | null
}

interface CharacteristicValue {
  tipo_id: number
  valor: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function GerarItensPage() {
  const router = useRouter()
  const [clients, setClients] = useState<Client[]>([])
  const [materials, setMaterials] = useState<Material[]>([])

  const [selectedClientId, setSelectedClientId] = useState<number | null>(null)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null)

  // Lista de conjuntos de características
  const [characteristicsSets, setCharacteristicsSets] = useState<CharacteristicValue[][]>([])
  const [currentSet, setCurrentSet] = useState<CharacteristicValue[]>([])

  const [result, setResult] = useState<{created: number, skipped: number, errors: string[]} | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchClients()
    fetchMaterials()
  }, [])

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
      setMaterials(data.items || [])
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

      // Inicializar conjunto atual com as características do material
      const initialSet = material.caracteristicas.map((c: Characteristic) => ({
        tipo_id: c.id,
        valor: ''
      }))
      setCurrentSet(initialSet)
    } catch (err) {
      console.error(err)
    }
  }

  const addCurrentSetToList = () => {
    // Validar se todos os campos estão preenchidos
    const allFilled = currentSet.every(c => c.valor.trim() !== '')
    if (!allFilled) {
      alert('Preencha todas as características antes de adicionar')
      return
    }

    setCharacteristicsSets([...characteristicsSets, currentSet])

    // Resetar conjunto atual
    const newSet = selectedMaterial!.caracteristicas.map((c: Characteristic) => ({
      tipo_id: c.id,
      valor: ''
    }))
    setCurrentSet(newSet)
  }

  const removeSet = (index: number) => {
    setCharacteristicsSets(characteristicsSets.filter((_, i) => i !== index))
  }

  const handleGenerate = async () => {
    if (!selectedClientId || !selectedMaterialId || characteristicsSets.length === 0) {
      alert('Selecione cliente, material e adicione pelo menos um conjunto de características')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/materials/items/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: selectedClientId,
          material_id: selectedMaterialId,
          caracteristicas_set: characteristicsSets
        })
      })

      const data = await res.json()
      setResult(data)

      if (data.created > 0) {
        alert(`${data.created} itens criados com sucesso! ${data.skipped} duplicados ignorados.`)
      }
    } catch (err: any) {
      alert('Erro ao gerar itens: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Gerar Itens em Lote</h1>
        <button
          onClick={() => router.push('/cadastros/itens')}
          className="px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          Voltar
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">1. Selecione o Cliente e Material</h2>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-1">Cliente *</label>
            <select
              value={selectedClientId || ''}
              onChange={(e) => setSelectedClientId(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-lg"
            >
              <option value="">Selecione...</option>
              {clients.map(c => (
                <option key={c.id} value={c.id}>{c.nome_curto || c.nome}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Material *</label>
            <select
              value={selectedMaterialId || ''}
              onChange={(e) => handleMaterialSelect(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-lg"
            >
              <option value="">Selecione...</option>
              {materials.map(m => (
                <option key={m.id} value={m.id}>{m.nome}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {selectedMaterial && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">2. Defina as Características</h2>

          {currentSet.map((char, idx) => {
            const charDef = selectedMaterial.caracteristicas[idx]
            return (
              <div key={idx} className="mb-3">
                <label className="block text-sm font-medium mb-1">{charDef.nome}</label>
                <input
                  type="text"
                  value={char.valor}
                  onChange={(e) => {
                    const updated = [...currentSet]
                    updated[idx].valor = e.target.value
                    setCurrentSet(updated)
                  }}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
            )
          })}

          <button
            onClick={addCurrentSetToList}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            + Adicionar à Lista
          </button>
        </div>
      )}

      {characteristicsSets.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            3. Itens a Gerar ({characteristicsSets.length})
          </h2>

          <div className="space-y-2">
            {characteristicsSets.map((set, idx) => (
              <div key={idx} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                <div className="flex gap-4">
                  {set.map((char, charIdx) => (
                    <span key={charIdx} className="text-sm">
                      <strong>{selectedMaterial!.caracteristicas[charIdx].nome}:</strong> {char.valor}
                    </span>
                  ))}
                </div>
                <button
                  onClick={() => removeSet(idx)}
                  className="text-red-600 hover:text-red-800"
                >
                  Remover
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading}
            className="mt-6 w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {loading ? 'Gerando...' : `Gerar ${characteristicsSets.length} Itens`}
          </button>
        </div>
      )}

      {result && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">Resultado</h2>
          <div className="space-y-2">
            <p className="text-green-600">✓ {result.created} itens criados</p>
            <p className="text-yellow-600">⊘ {result.skipped} duplicados ignorados</p>
            {result.errors.length > 0 && (
              <div>
                <p className="text-red-600">✗ {result.errors.length} erros:</p>
                <ul className="ml-4 text-sm text-red-600">
                  {result.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

### Adicionar link no menu Sidebar
```typescript
// Em components/Sidebar.tsx, na seção "Cadastros":
<Link
  href="/cadastros/itens/gerar"
  className="..."
>
  Gerar Itens em Lote
</Link>
```

## 4. Resumo das Mudanças

### Backend (✅ Completo)
- Migration 007 aplicada
- Modelos atualizados
- Schemas atualizados
- Endpoint de geração de itens criado
- Validação de unicidade implementada
- Hash de características funcionando

### Frontend (⚠️ Pendente)
- [ ] Atualizar formulário de Materiais
- [ ] Atualizar formulário de Itens
- [ ] Adicionar filtros por cliente
- [ ] Criar tela de geração em lote

## 5. Testes Recomendados

Após implementar as mudanças do frontend:

1. **Criar Material com Cliente**
   - Criar material vinculado a cliente
   - Definir código de 9 dígitos
   - Adicionar características

2. **Gerar Itens em Lote**
   - Selecionar cliente e material
   - Adicionar 5 conjuntos de características diferentes
   - Tentar adicionar 1 duplicado
   - Verificar que criou 5 e ignorou 1

3. **Validação de Unicidade**
   - Tentar criar item duplicado manualmente
   - Verificar mensagem de erro

4. **Filtros**
   - Filtrar materiais por cliente
   - Filtrar itens por cliente
   - Verificar que aparecem apenas os do cliente selecionado
