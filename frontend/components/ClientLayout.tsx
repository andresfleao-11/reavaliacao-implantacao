'use client'

import { AuthProvider } from '@/contexts/AuthContext'
import Sidebar from '@/components/Sidebar'
import ProtectedRoute from '@/components/ProtectedRoute'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isLoginPage = pathname === '/login'
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Durante SSR, renderizar apenas estrutura básica
  if (!mounted) {
    return (
      <AuthProvider>
        {children}
      </AuthProvider>
    )
  }

  return (
    <AuthProvider>
      {isLoginPage ? (
        <>{children}</>
      ) : (
        <ProtectedRoute>
          <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
            <Sidebar />
            <main className="flex-1 overflow-y-auto pt-16 lg:pt-0">
              <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 max-w-7xl">
                {children}
              </div>
            </main>
          </div>
        </ProtectedRoute>
      )}
    </AuthProvider>
  )
}
