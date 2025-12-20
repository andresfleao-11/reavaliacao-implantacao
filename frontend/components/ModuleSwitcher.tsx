'use client'

import { useState, useRef, useEffect } from 'react'
import { useModule, ModuleType } from '@/contexts/ModuleContext'

interface ModuleSwitcherProps {
  collapsed?: boolean
}

export default function ModuleSwitcher({ collapsed = false }: ModuleSwitcherProps) {
  const { activeModule, setActiveModule } = useModule()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const modules: { id: ModuleType; name: string; icon: JSX.Element; color: string }[] = [
    {
      id: 'reavaliacao',
      name: 'Reavaliação',
      color: 'text-blue-600 dark:text-blue-400',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      )
    },
    {
      id: 'inventario',
      name: 'Inventário',
      color: 'text-green-600 dark:text-green-400',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
        </svg>
      )
    }
  ]

  const currentModule = modules.find(m => m.id === activeModule) || modules[0]

  // Fechar dropdown ao clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleModuleChange = (moduleId: ModuleType) => {
    setActiveModule(moduleId)
    setIsOpen(false)
  }

  if (collapsed) {
    return (
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`w-full flex items-center justify-center p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${currentModule.color}`}
          title={currentModule.name}
        >
          {currentModule.icon}
        </button>

        {isOpen && (
          <div className="absolute left-full top-0 ml-2 w-48 bg-white dark:bg-gray-800 shadow-xl rounded-lg z-50 py-2 border border-gray-200 dark:border-gray-700">
            <div className="px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
              Selecionar Módulo
            </div>
            {modules.map((module) => (
              <button
                key={module.id}
                onClick={() => handleModuleChange(module.id)}
                className={`w-full flex items-center px-3 py-2.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                  module.id === activeModule
                    ? `${module.color} bg-gray-50 dark:bg-gray-700/50`
                    : 'text-gray-700 dark:text-gray-300'
                }`}
              >
                <span className={module.color}>{module.icon}</span>
                <span className="ml-3">{module.name}</span>
                {module.id === activeModule && (
                  <svg className="w-4 h-4 ml-auto text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors border border-gray-200 dark:border-gray-700`}
      >
        <div className="flex items-center">
          <span className={currentModule.color}>{currentModule.icon}</span>
          <span className={`ml-3 font-medium ${currentModule.color}`}>{currentModule.name}</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-white dark:bg-gray-800 shadow-xl rounded-lg z-50 py-2 border border-gray-200 dark:border-gray-700">
          {modules.map((module) => (
            <button
              key={module.id}
              onClick={() => handleModuleChange(module.id)}
              className={`w-full flex items-center px-4 py-2.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                module.id === activeModule
                  ? `${module.color} bg-gray-50 dark:bg-gray-700/50`
                  : 'text-gray-700 dark:text-gray-300'
              }`}
            >
              <span className={module.color}>{module.icon}</span>
              <span className="ml-3">{module.name}</span>
              {module.id === activeModule && (
                <svg className="w-4 h-4 ml-auto text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
