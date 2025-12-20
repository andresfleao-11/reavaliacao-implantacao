'use client'

import { useEffect, useState } from 'react'

interface UseServiceWorkerReturn {
  isSupported: boolean
  isRegistered: boolean
  registration: ServiceWorkerRegistration | null
  error: string | null
  update: () => Promise<void>
}

export function useServiceWorker(): UseServiceWorkerReturn {
  const [isSupported, setIsSupported] = useState(false)
  const [isRegistered, setIsRegistered] = useState(false)
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return

    // Check if service workers are supported
    if (!('serviceWorker' in navigator)) {
      setIsSupported(false)
      setError('Service Workers not supported in this browser')
      return
    }

    setIsSupported(true)

    // Register service worker
    const registerSW = async () => {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js', {
          scope: '/'
        })

        setRegistration(reg)
        setIsRegistered(true)
        console.log('[SW] Service worker registered:', reg.scope)

        // Check for updates
        reg.addEventListener('updatefound', () => {
          const newWorker = reg.installing
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                console.log('[SW] New content available, refresh to update')
              }
            })
          }
        })
      } catch (err: any) {
        console.error('[SW] Registration failed:', err)
        setError(err.message || 'Failed to register service worker')
      }
    }

    registerSW()

    // Handle messages from service worker
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'SYNC_OPPORTUNITY') {
        // Dispatch custom event for sync opportunity
        window.dispatchEvent(new CustomEvent('sw-sync-opportunity', {
          detail: { timestamp: event.data.timestamp }
        }))
      }
    }

    navigator.serviceWorker.addEventListener('message', handleMessage)

    return () => {
      navigator.serviceWorker.removeEventListener('message', handleMessage)
    }
  }, [])

  const update = async () => {
    if (registration) {
      await registration.update()
    }
  }

  return {
    isSupported,
    isRegistered,
    registration,
    error,
    update
  }
}

// Hook to cache session data for offline use
export function useCacheSession() {
  const cacheSession = async (sessionId: number, data: {
    session: any
    expectedAssets?: any[]
  }) => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return
    }

    const controller = navigator.serviceWorker.controller
    if (controller) {
      controller.postMessage({
        type: 'CACHE_SESSION',
        sessionId,
        data
      })
    }
  }

  return { cacheSession }
}
