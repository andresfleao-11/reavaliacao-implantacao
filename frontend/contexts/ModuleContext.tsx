'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'

export type ModuleType = 'reavaliacao' | 'inventario'

interface ModuleContextType {
  activeModule: ModuleType
  setActiveModule: (module: ModuleType) => void
  isInventoryModule: boolean
  isRevaluationModule: boolean
}

const ModuleContext = createContext<ModuleContextType | undefined>(undefined)

export function ModuleProvider({ children }: { children: ReactNode }) {
  const [activeModule, setActiveModuleState] = useState<ModuleType>('reavaliacao')
  const router = useRouter()
  const pathname = usePathname()

  // Carregar módulo salvo do localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedModule = localStorage.getItem('activeModule') as ModuleType | null
      if (savedModule && (savedModule === 'reavaliacao' || savedModule === 'inventario')) {
        setActiveModuleState(savedModule)
      }
    }
  }, [])

  // Detectar módulo baseado na URL
  useEffect(() => {
    if (pathname) {
      // Páginas exclusivas do inventário
      const inventoryPaths = [
        '/inventario/sessoes',
        '/inventario/bens',
        '/configuracoes/sistemas-externos'
      ]

      const isInventoryPath = inventoryPaths.some(path => pathname.startsWith(path))

      if (isInventoryPath && activeModule !== 'inventario') {
        setActiveModuleState('inventario')
        localStorage.setItem('activeModule', 'inventario')
      }
    }
  }, [pathname, activeModule])

  const setActiveModule = (module: ModuleType) => {
    setActiveModuleState(module)
    localStorage.setItem('activeModule', module)

    // Redirecionar para a página inicial do módulo selecionado
    if (module === 'inventario') {
      router.push('/inventario/sessoes')
    } else {
      router.push('/cotacao')
    }
  }

  return (
    <ModuleContext.Provider
      value={{
        activeModule,
        setActiveModule,
        isInventoryModule: activeModule === 'inventario',
        isRevaluationModule: activeModule === 'reavaliacao'
      }}
    >
      {children}
    </ModuleContext.Provider>
  )
}

export function useModule() {
  const context = useContext(ModuleContext)
  if (context === undefined) {
    throw new Error('useModule must be used within a ModuleProvider')
  }
  return context
}
