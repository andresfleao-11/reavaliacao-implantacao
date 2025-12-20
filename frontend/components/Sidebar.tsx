'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useModule } from '@/contexts/ModuleContext'
import ModuleSwitcher from '@/components/ModuleSwitcher'

export default function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const { activeModule, isInventoryModule, isRevaluationModule } = useModule()
  const [configOpen, setConfigOpen] = useState(false)
  const [cadastrosOpen, setCadastrosOpen] = useState(false)
  const [cotacaoOpen, setCotacaoOpen] = useState(false)
  const [ferramentasOpen, setFerramentasOpen] = useState(false)
  const [inventarioOpen, setInventarioOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  // Hover states para submenus no modo collapsed
  const [hoverCotacao, setHoverCotacao] = useState(false)
  const [hoverCadastros, setHoverCadastros] = useState(false)
  const [hoverFerramentas, setHoverFerramentas] = useState(false)
  const [hoverConfig, setHoverConfig] = useState(false)
  const [hoverInventario, setHoverInventario] = useState(false)

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

  // Fechar menu mobile ao navegar
  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

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

  // Componente de submenu para modo collapsed (hover)
  const CollapsedSubmenu = ({
    children,
    isHovered,
    onMouseEnter,
    onMouseLeave
  }: {
    children: React.ReactNode
    isHovered: boolean
    onMouseEnter: () => void
    onMouseLeave: () => void
  }) => {
    if (!collapsed || !isHovered) return null
    return (
      <div
        className="absolute left-full top-0 ml-1 w-56 bg-white dark:bg-gray-800 shadow-xl rounded-lg z-50 py-2 border border-gray-200 dark:border-gray-700"
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
      >
        {children}
      </div>
    )
  }

  // Componente de item do submenu
  const SubmenuItem = ({ href, label, isCollapsed = false }: { href: string; label: string; isCollapsed?: boolean }) => (
    <Link
      href={href}
      onClick={() => setMobileOpen(false)}
      className={`flex items-center ${isCollapsed ? 'px-4' : 'px-12'} py-2.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-primary-50 dark:hover:bg-gray-700 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
        pathname === href ? 'bg-primary-50 dark:bg-gray-700 text-primary-600 dark:text-primary-400' : ''
      }`}
    >
      {label}
    </Link>
  )

  // Componente de menu com submenu
  const MenuWithSubmenu = ({
    icon,
    label,
    isOpen,
    setIsOpen,
    isHovered,
    setIsHovered,
    isActiveCheck,
    children
  }: {
    icon: React.ReactNode
    label: string
    isOpen: boolean
    setIsOpen: (open: boolean) => void
    isHovered: boolean
    setIsHovered: (hovered: boolean) => void
    isActiveCheck: boolean
    children: React.ReactNode
  }) => (
    <div
      className="relative"
      onMouseEnter={() => collapsed && setIsHovered(true)}
      onMouseLeave={() => collapsed && setIsHovered(false)}
    >
      <button
        onClick={() => !collapsed && setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
          isActiveCheck ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
        }`}
        title={collapsed ? label : ''}
      >
        <div className="flex items-center">
          {icon}
          <span className={`ml-3 ${collapsed ? 'hidden' : ''}`}>{label}</span>
        </div>
        {!collapsed && (
          <svg
            className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {/* Submenu expandido (modo não collapsed) */}
      {!collapsed && isOpen && (
        <div className="bg-gray-50 dark:bg-gray-800">
          {children}
        </div>
      )}

      {/* Submenu hover (modo collapsed) */}
      <CollapsedSubmenu
        isHovered={isHovered}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {children}
      </CollapsedSubmenu>
    </div>
  )

  // Conteúdo do menu (compartilhado entre desktop e mobile)
  const MenuContent = ({ isMobile = false }: { isMobile?: boolean }) => (
    <>
      {/* ============ MENUS DO MÓDULO REAVALIAÇÃO ============ */}
      {isRevaluationModule && (
        <>
          {/* Cotacao - Submenu */}
          {isMobile ? (
            <div>
              <button
                onClick={() => setCotacaoOpen(!cotacaoOpen)}
                className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                  isActive('/cotacao') || isActive('/historico') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                }`}
              >
                <div className="flex items-center">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <span className="ml-3">Cotação</span>
                </div>
                <svg className={`w-4 h-4 transition-transform ${cotacaoOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {cotacaoOpen && (
                <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                  <SubmenuItem href="/cotacao" label="Nova Cotação" />
                  <SubmenuItem href="/cotacao/lote" label="Cotação em Lote" />
                  <SubmenuItem href="/cotacao/lote/historico" label="Histórico de Lote" />
                  <SubmenuItem href="/historico" label="Histórico" />
                </div>
              )}
            </div>
          ) : (
            <MenuWithSubmenu
              icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>}
              label="Cotação"
              isOpen={cotacaoOpen}
              setIsOpen={setCotacaoOpen}
              isHovered={hoverCotacao}
              setIsHovered={setHoverCotacao}
              isActiveCheck={isActive('/cotacao') || isActive('/historico')}
            >
              <SubmenuItem href="/cotacao" label="Nova Cotação" isCollapsed={collapsed} />
              <SubmenuItem href="/cotacao/lote" label="Cotação em Lote" isCollapsed={collapsed} />
              <SubmenuItem href="/cotacao/lote/historico" label="Histórico de Lote" isCollapsed={collapsed} />
              <SubmenuItem href="/historico" label="Histórico" isCollapsed={collapsed} />
            </MenuWithSubmenu>
          )}

          {/* Projetos - Menu principal - apenas para ADMIN */}
          {userRole === 'ADMIN' && (
            <Link
              href="/cadastros/projetos"
              onClick={() => setMobileOpen(false)}
              className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                isActive('/cadastros/projetos') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
              }`}
              title={collapsed && !isMobile ? 'Projetos' : ''}
            >
              <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span className={`ml-3 ${collapsed && !isMobile ? 'hidden' : ''}`}>Projetos</span>
            </Link>
          )}

          {/* Cadastros - apenas para ADMIN */}
          {userRole === 'ADMIN' && (
            isMobile ? (
              <div>
                <button
                  onClick={() => setCadastrosOpen(!cadastrosOpen)}
                  className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                    isActive('/cadastros') || isActive('/admin') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  <div className="flex items-center">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    <span className="ml-3">Cadastros</span>
                  </div>
                  <svg className={`w-4 h-4 transition-transform ${cadastrosOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {cadastrosOpen && (
                  <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                    <SubmenuItem href="/cadastros/clientes" label="Clientes" />
                    <SubmenuItem href="/cadastros/materiais" label="Materiais e Características" />
                    <SubmenuItem href="/cadastros/itens" label="Itens" />
                    <SubmenuItem href="/cadastros/itens/gerar" label="Gerar Itens em Lote" />
                    {userRole === 'ADMIN' && <SubmenuItem href="/admin/usuarios" label="Usuários" />}
                  </div>
                )}
              </div>
            ) : (
              <MenuWithSubmenu
                icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>}
                label="Cadastros"
                isOpen={cadastrosOpen}
                setIsOpen={setCadastrosOpen}
                isHovered={hoverCadastros}
                setIsHovered={setHoverCadastros}
                isActiveCheck={isActive('/cadastros') || isActive('/admin')}
              >
                <SubmenuItem href="/cadastros/clientes" label="Clientes" isCollapsed={collapsed} />
                <SubmenuItem href="/cadastros/materiais" label="Materiais e Características" isCollapsed={collapsed} />
                <SubmenuItem href="/cadastros/itens" label="Itens" isCollapsed={collapsed} />
                <SubmenuItem href="/cadastros/itens/gerar" label="Gerar Itens em Lote" isCollapsed={collapsed} />
                {userRole === 'ADMIN' && <SubmenuItem href="/admin/usuarios" label="Usuários" isCollapsed={collapsed} />}
              </MenuWithSubmenu>
            )
          )}

          {/* Financeiro - Menu principal para ADMIN */}
          {userRole === 'ADMIN' && (
            <Link
              href="/admin/financeiro"
              onClick={() => setMobileOpen(false)}
              className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
                isActive('/admin/financeiro') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
              }`}
              title={collapsed && !isMobile ? 'Financeiro' : ''}
            >
              <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className={`ml-3 ${collapsed && !isMobile ? 'hidden' : ''}`}>Financeiro</span>
            </Link>
          )}

          {/* Inventário antigo (leitura RFID) - Submenu - apenas para ADMIN em modo Reavaliação */}
          {userRole === 'ADMIN' && (isMobile ? (
            <div>
              <button
                onClick={() => setInventarioOpen(!inventarioOpen)}
                className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                  isActive('/inventario') && !isActive('/inventario/sessoes') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                }`}
              >
                <div className="flex items-center">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                  </svg>
                  <span className="ml-3">Leitura RFID</span>
                </div>
                <svg className={`w-4 h-4 transition-transform ${inventarioOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {inventarioOpen && (
                <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                  <SubmenuItem href="/inventario" label="Nova Leitura" />
                  <SubmenuItem href="/inventario/historico" label="Histórico de Leituras" />
                </div>
              )}
            </div>
          ) : (
            <MenuWithSubmenu
              icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>}
              label="Leitura RFID"
              isOpen={inventarioOpen}
              setIsOpen={setInventarioOpen}
              isHovered={hoverInventario}
              setIsHovered={setHoverInventario}
              isActiveCheck={isActive('/inventario') && !isActive('/inventario/sessoes')}
            >
              <SubmenuItem href="/inventario" label="Nova Leitura" isCollapsed={collapsed} />
              <SubmenuItem href="/inventario/historico" label="Histórico de Leituras" isCollapsed={collapsed} />
            </MenuWithSubmenu>
          ))}

          {/* Ferramentas - Submenu - apenas para ADMIN */}
          {userRole === 'ADMIN' && (
            isMobile ? (
              <div>
                <button
                  onClick={() => setFerramentasOpen(!ferramentasOpen)}
                  className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                    isActive('/configuracoes/banco-precos') || isActive('/configuracoes/banco-precos-veiculos') || isActive('/admin/debug-serpapi') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  <div className="flex items-center">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                    </svg>
                    <span className="ml-3">Ferramentas</span>
                  </div>
                  <svg className={`w-4 h-4 transition-transform ${ferramentasOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {ferramentasOpen && (
                  <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                    <SubmenuItem href="/configuracoes/banco-precos" label="Banco de Preços" />
                    <SubmenuItem href="/configuracoes/banco-precos-veiculos" label="Banco Preços Veículos" />
                    <SubmenuItem href="/admin/debug-serpapi" label="Debug SerpAPI" />
                  </div>
                )}
              </div>
            ) : (
              <MenuWithSubmenu
                icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" /></svg>}
                label="Ferramentas"
                isOpen={ferramentasOpen}
                setIsOpen={setFerramentasOpen}
                isHovered={hoverFerramentas}
                setIsHovered={setHoverFerramentas}
                isActiveCheck={isActive('/configuracoes/banco-precos') || isActive('/configuracoes/banco-precos-veiculos') || isActive('/admin/debug-serpapi')}
              >
                <SubmenuItem href="/configuracoes/banco-precos" label="Banco de Preços" isCollapsed={collapsed} />
                <SubmenuItem href="/configuracoes/banco-precos-veiculos" label="Banco Preços Veículos" isCollapsed={collapsed} />
                <SubmenuItem href="/admin/debug-serpapi" label="Debug SerpAPI" isCollapsed={collapsed} />
              </MenuWithSubmenu>
            )
          )}

          {/* Configurações - Reavaliação */}
          {isMobile ? (
            <div>
              <button
                onClick={() => setConfigOpen(!configOpen)}
                className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                  isActive('/configuracoes') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                }`}
              >
                <div className="flex items-center">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="ml-3">Configurações</span>
                </div>
                <svg className={`w-4 h-4 transition-transform ${configOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {configOpen && (
                <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                  <SubmenuItem href="/configuracoes/parametros" label="Parâmetros" />
                  <SubmenuItem href="/configuracoes/fator-reavaliacao" label="Fator de Reavaliação" />
                  <SubmenuItem href="/configuracoes/integracoes" label="Integrações" />
                </div>
              )}
            </div>
          ) : (
            <MenuWithSubmenu
              icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>}
              label="Configurações"
              isOpen={configOpen}
              setIsOpen={setConfigOpen}
              isHovered={hoverConfig}
              setIsHovered={setHoverConfig}
              isActiveCheck={isActive('/configuracoes')}
            >
              <SubmenuItem href="/configuracoes/parametros" label="Parâmetros" isCollapsed={collapsed} />
              <SubmenuItem href="/configuracoes/fator-reavaliacao" label="Fator de Reavaliação" isCollapsed={collapsed} />
              <SubmenuItem href="/configuracoes/integracoes" label="Integrações" isCollapsed={collapsed} />
            </MenuWithSubmenu>
          )}
        </>
      )}

      {/* ============ MENUS DO MÓDULO INVENTÁRIO ============ */}
      {isInventoryModule && (
        <>
          {/* Sessões de Inventário - Menu principal */}
          <Link
            href="/inventario/sessoes"
            onClick={() => setMobileOpen(false)}
            className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
              isActive('/inventario/sessoes') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
            }`}
            title={collapsed && !isMobile ? 'Sessões de Inventário' : ''}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
            <span className={`ml-3 ${collapsed && !isMobile ? 'hidden' : ''}`}>Sessões de Inventário</span>
          </Link>

          {/* Bens Cadastrados - Menu principal */}
          <Link
            href="/inventario/bens"
            onClick={() => setMobileOpen(false)}
            className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
              isActive('/inventario/bens') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
            }`}
            title={collapsed && !isMobile ? 'Bens Cadastrados' : ''}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span className={`ml-3 ${collapsed && !isMobile ? 'hidden' : ''}`}>Bens Cadastrados</span>
          </Link>

          {/* Cadastros - Módulo Inventário */}
          {userRole === 'ADMIN' && (
            isMobile ? (
              <div>
                <button
                  onClick={() => setCadastrosOpen(!cadastrosOpen)}
                  className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                    isActive('/cadastros/clientes') || isActive('/admin/usuarios') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                  }`}
                >
                  <div className="flex items-center">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                    <span className="ml-3">Cadastros</span>
                  </div>
                  <svg className={`w-4 h-4 transition-transform ${cadastrosOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {cadastrosOpen && (
                  <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                    <SubmenuItem href="/cadastros/clientes" label="Clientes" />
                    <SubmenuItem href="/admin/usuarios" label="Usuários" />
                  </div>
                )}
              </div>
            ) : (
              <MenuWithSubmenu
                icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>}
                label="Cadastros"
                isOpen={cadastrosOpen}
                setIsOpen={setCadastrosOpen}
                isHovered={hoverCadastros}
                setIsHovered={setHoverCadastros}
                isActiveCheck={isActive('/cadastros/clientes') || isActive('/admin/usuarios')}
              >
                <SubmenuItem href="/cadastros/clientes" label="Clientes" isCollapsed={collapsed} />
                <SubmenuItem href="/admin/usuarios" label="Usuários" isCollapsed={collapsed} />
              </MenuWithSubmenu>
            )
          )}

          {/* Configurações - Módulo Inventário */}
          {isMobile ? (
            <div>
              <button
                onClick={() => setConfigOpen(!configOpen)}
                className={`w-full flex items-center justify-between px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 ${
                  isActive('/configuracoes/sistemas-externos') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400' : ''
                }`}
              >
                <div className="flex items-center">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="ml-3">Configurações</span>
                </div>
                <svg className={`w-4 h-4 transition-transform ${configOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {configOpen && (
                <div className="bg-gray-50 dark:bg-gray-800 pl-4">
                  <SubmenuItem href="/configuracoes/sistemas-externos" label="Sistemas Externos" />
                </div>
              )}
            </div>
          ) : (
            <MenuWithSubmenu
              icon={<svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>}
              label="Configurações"
              isOpen={configOpen}
              setIsOpen={setConfigOpen}
              isHovered={hoverConfig}
              setIsHovered={setHoverConfig}
              isActiveCheck={isActive('/configuracoes/sistemas-externos')}
            >
              <SubmenuItem href="/configuracoes/sistemas-externos" label="Sistemas Externos" isCollapsed={collapsed} />
            </MenuWithSubmenu>
          )}
        </>
      )}

      {/* Conta */}
      <Link
        href="/conta"
        onClick={() => setMobileOpen(false)}
        className={`flex items-center px-6 py-3 text-gray-700 dark:text-gray-200 hover:bg-primary-50 dark:hover:bg-gray-800 hover:text-primary-600 dark:hover:text-primary-400 transition-colors ${
          isActive('/conta') ? 'bg-primary-50 dark:bg-gray-800 text-primary-600 dark:text-primary-400 border-r-4 border-primary-600 dark:border-primary-400' : ''
        }`}
        title={collapsed && !isMobile ? 'Minha Conta' : ''}
      >
        <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        <span className={`ml-3 ${collapsed && !isMobile ? 'hidden' : ''}`}>Minha Conta</span>
      </Link>

      {/* Sair */}
      <button
        onClick={() => { setMobileOpen(false); logout(); }}
        className="flex items-center w-full px-6 py-3 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        title={collapsed && !isMobile ? 'Sair' : ''}
      >
        <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
        <span className={`ml-3 ${collapsed && !isMobile ? 'hidden' : ''}`}>Sair</span>
      </button>
    </>
  )

  return (
    <>
      {/* ============ MOBILE HEADER ============ */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-white dark:bg-gray-900 shadow-md h-16 flex items-center justify-between px-4">
        {/* Botão hamburger */}
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
          aria-label="Abrir menu"
        >
          <svg className="w-6 h-6 text-gray-700 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Logo central */}
        <h1 className="text-lg font-bold text-primary-600 dark:text-primary-400">Reavaliação Patrimonial</h1>

        {/* Botão tema */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
          aria-label={theme === 'light' ? 'Modo Escuro' : 'Modo Claro'}
        >
          {theme === 'light' ? (
            <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          )}
        </button>
      </header>

      {/* ============ MOBILE DRAWER ============ */}
      {/* Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-50"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Drawer */}
      <aside
        className={`lg:hidden fixed inset-y-0 left-0 z-50 w-80 max-w-[85vw] bg-white dark:bg-gray-900 shadow-xl transform transition-transform duration-300 ease-in-out flex flex-col ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header do drawer com botão fechar */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-bold text-primary-600 dark:text-primary-400">Menu</h2>
          <button
            onClick={() => setMobileOpen(false)}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Fechar menu"
          >
            <svg className="w-6 h-6 text-gray-700 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Module Switcher Mobile */}
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <ModuleSwitcher collapsed={false} />
        </div>

        {/* Menu items */}
        <nav className="flex-1 overflow-y-auto py-4">
          <MenuContent isMobile={true} />
        </nav>

        {/* Footer com logo */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 flex justify-center">
          <img
            src="/logo.png"
            alt="Logo"
            className="w-10 h-10 object-contain"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        </div>
      </aside>

      {/* ============ DESKTOP SIDEBAR ============ */}
      <aside
        className={`hidden lg:flex fixed inset-y-0 left-0 z-30 bg-white dark:bg-gray-900 shadow-lg flex-col transition-all duration-300 ${
          collapsed ? 'w-20' : 'w-64'
        }`}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between h-16">
          {!collapsed && (
            <h1 className="text-lg font-bold text-primary-600 dark:text-primary-400 truncate">
              Reavaliação Patrimonial
            </h1>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={`p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 ${collapsed ? 'mx-auto' : ''}`}
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
          >
            <svg
              className={`w-5 h-5 text-gray-600 dark:text-gray-300 transition-transform ${collapsed ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>

        {/* Module Switcher */}
        <div className="px-3 py-3 border-b border-gray-200 dark:border-gray-700">
          <ModuleSwitcher collapsed={collapsed} />
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4">
          <MenuContent isMobile={false} />
        </nav>

        {/* Footer com logo e botão de tema */}
        <div className="border-t border-gray-200 dark:border-gray-700">
          {/* Logo */}
          <div className="p-4 flex justify-center">
            <img
              src="/logo.png"
              alt="Logo"
              className="w-10 h-10 object-contain"
              onError={(e) => { e.currentTarget.style.display = 'none' }}
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
                  {!collapsed && <span className="ml-3 text-sm text-gray-700 dark:text-gray-200">Modo Escuro</span>}
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 flex-shrink-0 text-gray-700 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                  {!collapsed && <span className="ml-3 text-sm text-gray-700 dark:text-gray-200">Modo Claro</span>}
                </>
              )}
            </button>
          </div>
        </div>
      </aside>

      {/* Spacer para conteúdo principal - Desktop (empurra o main para a direita) */}
      <div className={`hidden lg:block flex-shrink-0 transition-all duration-300 ${collapsed ? 'w-20' : 'w-64'}`} />
    </>
  )
}
