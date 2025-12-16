'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'

export default function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [configOpen, setConfigOpen] = useState(false)
  const [cadastrosOpen, setCadastrosOpen] = useState(false)
  const [cotacaoOpen, setCotacaoOpen] = useState(false)
  const [ferramentasOpen, setFerramentasOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  // Usar role do usuário autenticado
  const userRole = user?.role || 'USER'

  // Carregar tema salvo (apenas no cliente)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
      if (savedTheme) {
        setTheme(savedTheme)
        document.documentElement.classList.toggle('dark', savedTheme === 'dark')
      }
    }
  }, [])

  // Alternar tema
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.classList.toggle('dark', newTheme === 'dark')
  }

  const isActive = (path: string) => {
    return pathname === path || pathname?.startsWith(path + '/')
  }

  return (
    <>
      {/* Overlay mobile */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Botão menu mobile */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg bg-white dark:bg-gray-800 shadow-lg"
      >
        <svg className="w-6 h-6 text-gray-700 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 bg-white dark:bg-gray-900 shadow-lg transition-all duration-300 flex flex-col
          ${collapsed ? 'lg:w-20' : 'lg:w-64'}
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          w-64`}
      >
        {/* Header */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className={`flex items-center ${collapsed ? 'lg:hidden' : ''}`}>
            <div>
              <h1 className="text-xl font-bold text-primary-600 dark:text-primary-400">Reavaliação Patrimonial</h1>
            </div>
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:block p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <svg className={`w-5 h-5 text-gray-600 dark:text-gray-300 transition-transform ${collapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="mt-6 flex-1 overflow-y-auto">
          {/* Cotacao - Submenu */}
          <div className="relative">
            <button
              onClick={() => setCotacaoOpen(!cotacaoOpen)}
              onMouseEnter={() => collapsed && setCotacaoOpen(true)}
              onMouseLeave={() => collapsed && setCotacaoOpen(false)}
              className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                isActive('/cotacao') || isActive('/historico') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
              }`}
              title={collapsed ? 'Cotacao' : ''}
            >
              <div className="flex items-center">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Cotacao</span>
              </div>
              <svg
                className={`w-4 h-4 transition-transform ${cotacaoOpen ? 'rotate-180' : ''} ${collapsed ? 'lg:hidden' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {cotacaoOpen && (
              <div
                className={`${
                  collapsed
                    ? 'hidden lg:block absolute left-full top-0 ml-2 w-56 bg-white dark:bg-gray-800 shadow-lg rounded-lg z-50 py-2'
                    : 'bg-gray-50 dark:bg-gray-800'
                }`}
                onMouseEnter={() => collapsed && setCotacaoOpen(true)}
                onMouseLeave={() => collapsed && setCotacaoOpen(false)}
              >
                <Link
                  href="/cotacao"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/cotacao' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Nova Cotacao
                </Link>
                <Link
                  href="/cotacao/lote"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/cotacao/lote' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Cotacao em Lote
                </Link>
                <Link
                  href="/cotacao/lote/historico"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/cotacao/lote/historico' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Historico de Lote
                </Link>
                <Link
                  href="/historico"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/historico' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Historico
                </Link>
              </div>
            )}
          </div>

          {/* Projetos - Menu principal - apenas para ADMIN */}
          {userRole === 'ADMIN' && (
            <Link
              href="/cadastros/projetos"
              className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                isActive('/cadastros/projetos') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
              }`}
              title={collapsed ? 'Projetos' : ''}
            >
              <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Projetos</span>
            </Link>
          )}

          {/* Cadastros - apenas para ADMIN */}
          {userRole === 'ADMIN' && (
            <div className="relative">
              <button
                onClick={() => setCadastrosOpen(!cadastrosOpen)}
                onMouseEnter={() => collapsed && setCadastrosOpen(true)}
                onMouseLeave={() => collapsed && setCadastrosOpen(false)}
                className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                  isActive('/cadastros') || isActive('/admin') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                }`}
                title={collapsed ? 'Cadastros' : ''}
              >
                <div className="flex items-center">
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Cadastros</span>
                </div>
                <svg
                  className={`w-4 h-4 transition-transform ${cadastrosOpen ? 'rotate-180' : ''} ${collapsed ? 'lg:hidden' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {cadastrosOpen && (
                <div
                  className={`${
                    collapsed
                      ? 'hidden lg:block absolute left-full top-0 ml-2 w-56 bg-white dark:bg-gray-800 shadow-lg rounded-lg z-50 py-2'
                      : 'bg-gray-50 dark:bg-gray-800'
                  }`}
                  onMouseEnter={() => collapsed && setCadastrosOpen(true)}
                  onMouseLeave={() => collapsed && setCadastrosOpen(false)}
                >
                  <Link
                    href="/cadastros/clientes"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/cadastros/clientes' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Clientes
                  </Link>
                  <Link
                    href="/cadastros/materiais"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/cadastros/materiais' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Materiais e Características
                  </Link>
                  <Link
                    href="/cadastros/itens"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/cadastros/itens' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Itens
                  </Link>
                  <Link
                    href="/cadastros/itens/gerar"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/cadastros/itens/gerar' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Gerar Itens em Lote
                  </Link>

                  {/* Usuários - apenas para ADMIN */}
                  {userRole === 'ADMIN' && (
                    <Link
                      href="/admin/usuarios"
                      className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                        pathname === '/admin/usuarios' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                      }`}
                    >
                      Usuários
                    </Link>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Financeiro - Menu principal para ADMIN */}
          {userRole === 'ADMIN' && (
            <Link
              href="/admin/financeiro"
              className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                isActive('/admin/financeiro') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
              }`}
              title={collapsed ? 'Financeiro' : ''}
            >
              <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Financeiro</span>
            </Link>
          )}

          {/* Ferramentas - Submenu - apenas para ADMIN */}
          {userRole === 'ADMIN' && (
            <div className="relative">
              <button
                onClick={() => setFerramentasOpen(!ferramentasOpen)}
                onMouseEnter={() => collapsed && setFerramentasOpen(true)}
                onMouseLeave={() => collapsed && setFerramentasOpen(false)}
                className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                  isActive('/configuracoes/banco-precos') || isActive('/configuracoes/banco-precos-veiculos') || isActive('/admin/debug-serpapi') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                }`}
                title={collapsed ? 'Ferramentas' : ''}
              >
                <div className="flex items-center">
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Ferramentas</span>
                </div>
                <svg
                  className={`w-4 h-4 transition-transform ${ferramentasOpen ? 'rotate-180' : ''} ${collapsed ? 'lg:hidden' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {ferramentasOpen && (
                <div
                  className={`${
                    collapsed
                      ? 'hidden lg:block absolute left-full top-0 ml-2 w-56 bg-white dark:bg-gray-800 shadow-lg rounded-lg z-50 py-2'
                      : 'bg-gray-50 dark:bg-gray-800'
                  }`}
                  onMouseEnter={() => collapsed && setFerramentasOpen(true)}
                  onMouseLeave={() => collapsed && setFerramentasOpen(false)}
                >
                  <Link
                    href="/configuracoes/banco-precos"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/configuracoes/banco-precos' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Banco de Preços
                  </Link>
                  <Link
                    href="/configuracoes/banco-precos-veiculos"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/configuracoes/banco-precos-veiculos' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Banco Preços Veículos
                  </Link>
                  <Link
                    href="/admin/debug-serpapi"
                    className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                      pathname === '/admin/debug-serpapi' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                    }`}
                  >
                    Debug SerpAPI
                  </Link>
                </div>
              )}
            </div>
          )}

          {/* Configurações */}
          <div className="relative">
            <button
              onClick={() => setConfigOpen(!configOpen)}
              onMouseEnter={() => collapsed && setConfigOpen(true)}
              onMouseLeave={() => collapsed && setConfigOpen(false)}
              className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                isActive('/configuracoes') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
              }`}
              title={collapsed ? 'Configurações' : ''}
            >
              <div className="flex items-center">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Configurações</span>
              </div>
              <svg
                className={`w-4 h-4 transition-transform ${configOpen ? 'rotate-180' : ''} ${collapsed ? 'lg:hidden' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {configOpen && (
              <div
                className={`${
                  collapsed
                    ? 'hidden lg:block absolute left-full top-0 ml-2 w-56 bg-white dark:bg-gray-800 shadow-lg rounded-lg z-50 py-2'
                    : 'bg-gray-50 dark:bg-gray-800'
                }`}
                onMouseEnter={() => collapsed && setConfigOpen(true)}
                onMouseLeave={() => collapsed && setConfigOpen(false)}
              >
                <Link
                  href="/configuracoes/parametros"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/configuracoes/parametros' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Parâmetros
                </Link>
                <Link
                  href="/configuracoes/fator-reavaliacao"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/configuracoes/fator-reavaliacao' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Fator de Reavaliação
                </Link>
                <Link
                  href="/configuracoes/integracoes"
                  className={`flex items-center ${collapsed ? 'px-4' : 'px-12'} py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                    pathname === '/configuracoes/integracoes' ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  Integrações
                </Link>
              </div>
            )}
          </div>

          {/* Conta */}
          <Link
            href="/conta"
            className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
              isActive('/conta') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
            }`}
            title={collapsed ? 'Minha Conta' : ''}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Minha Conta</span>
          </Link>

          {/* Sair */}
          <button
            onClick={logout}
            className="flex items-center w-full px-6 py-3 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            title={collapsed ? 'Sair' : ''}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span className={`ml-3 ${collapsed ? 'lg:hidden' : ''}`}>Sair</span>
          </button>
        </nav>

        {/* Footer com logo e botão de tema */}
        <div className="border-t border-gray-200 dark:border-gray-700">
          {/* Logo */}
          <div className={`p-4 flex ${collapsed ? 'justify-center' : 'justify-center'} items-center`}>
            <img
              src="/logo.png"
              alt="Logo"
              className="w-10 h-10 object-contain"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
            />
          </div>

          {/* Botão de tema */}
          <div className="p-4 pt-0">
            <button
              onClick={toggleTheme}
              className={`w-full flex items-center ${collapsed ? 'justify-center' : 'justify-start'} px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors`}
              title={collapsed ? (theme === 'light' ? 'Modo Escuro' : 'Modo Claro') : ''}
            >
              {theme === 'light' ? (
                <>
                  <svg className="w-5 h-5 flex-shrink-0 text-gray-700 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                  <span className={`ml-3 text-sm text-gray-700 dark:text-gray-200 ${collapsed ? 'lg:hidden' : ''}`}>Modo Escuro</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 flex-shrink-0 text-gray-700 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                  <span className={`ml-3 text-sm text-gray-700 dark:text-gray-200 ${collapsed ? 'lg:hidden' : ''}`}>Modo Claro</span>
                </>
              )}
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
