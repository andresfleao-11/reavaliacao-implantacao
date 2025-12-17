'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'

// Função para garantir que a URL tenha protocolo
const getApiUrl = () => {
  let url = process.env.NEXT_PUBLIC_API_URL || ''

  // Se não tiver variável ou estiver no Railway, usar URL do backend
  if (!url || (typeof window !== 'undefined' && window.location.hostname.includes('railway.app'))) {
    url = 'https://backend-production-78bb.up.railway.app'
  }

  // Garantir que tenha protocolo
  if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
    url = 'https://' + url
  }

  // Fallback para localhost em desenvolvimento
  return url || 'http://localhost:8000'
}

const API_URL = getApiUrl()

interface User {
  id: number
  email: string
  nome: string
  role: string
  ativo: boolean
  created_at: string
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Verificar se há usuário salvo no localStorage (apenas no cliente)
    if (typeof window !== 'undefined') {
      const savedUser = localStorage.getItem('user')
      if (savedUser) {
        try {
          setUser(JSON.parse(savedUser))
        } catch (error) {
          console.error('Error parsing saved user:', error)
          localStorage.removeItem('user')
        }
      }
    }
    setLoading(false)
  }, [])

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/api/users/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    })

    if (!res.ok) {
      const errData = await res.json()
      throw new Error(errData.detail || 'Erro ao fazer login')
    }

    const data = await res.json()

    // Salvar usuário e token
    setUser(data.user)
    localStorage.setItem('user', JSON.stringify(data.user))
    localStorage.setItem('access_token', data.access_token)

    router.push('/')
  }

  const logout = () => {
    setUser(null)
    localStorage.removeItem('user')
    localStorage.removeItem('access_token')
    router.push('/login')
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
