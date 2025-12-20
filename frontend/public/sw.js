/**
 * Service Worker para o módulo de inventário
 * Cache de assets estáticos e suporte offline
 */

const CACHE_NAME = 'inventory-cache-v1'
const STATIC_CACHE = 'inventory-static-v1'
const DYNAMIC_CACHE = 'inventory-dynamic-v1'

// Assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/inventario',
  '/inventario/sessoes',
  '/manifest.json'
]

// API endpoints to cache for offline
const API_CACHE_PATTERNS = [
  /\/api\/inventory\/sessions\/\d+$/,
  /\/api\/inventory\/sessions\/\d+\/expected/,
  /\/api\/inventory\/sessions\/\d+\/statistics/
]

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...')
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Caching static assets')
        // Only cache if available
        return cache.addAll(STATIC_ASSETS).catch((err) => {
          console.warn('[SW] Failed to cache some static assets:', err)
        })
      })
      .then(() => self.skipWaiting())
  )
})

// Activate event - cleanup old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...')
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== DYNAMIC_CACHE)
          .map((name) => {
            console.log('[SW] Deleting old cache:', name)
            return caches.delete(name)
          })
      )
    }).then(() => self.clients.claim())
  )
})

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return
  }

  // Handle API requests
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request))
    return
  }

  // Handle static assets with network-first strategy
  event.respondWith(handleStaticRequest(request))
})

async function handleStaticRequest(request) {
  try {
    // Try network first
    const networkResponse = await fetch(request)

    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE)
      cache.put(request, networkResponse.clone())
    }

    return networkResponse
  } catch (error) {
    // Fall back to cache
    const cachedResponse = await caches.match(request)
    if (cachedResponse) {
      return cachedResponse
    }

    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      const offlineResponse = await caches.match('/inventario')
      if (offlineResponse) {
        return offlineResponse
      }
    }

    throw error
  }
}

async function handleApiRequest(request) {
  const url = new URL(request.url)
  const shouldCache = API_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname))

  try {
    // Try network first
    const networkResponse = await fetch(request)

    // Cache successful GET responses for allowed patterns
    if (networkResponse.ok && shouldCache) {
      const cache = await caches.open(DYNAMIC_CACHE)
      cache.put(request, networkResponse.clone())
    }

    return networkResponse
  } catch (error) {
    // Fall back to cache for allowed patterns
    if (shouldCache) {
      const cachedResponse = await caches.match(request)
      if (cachedResponse) {
        // Add header to indicate this is a cached response
        const headers = new Headers(cachedResponse.headers)
        headers.set('X-From-Cache', 'true')
        return new Response(cachedResponse.body, {
          status: cachedResponse.status,
          statusText: cachedResponse.statusText,
          headers
        })
      }
    }

    // Return error response for offline API requests
    return new Response(
      JSON.stringify({
        error: 'offline',
        message: 'Sem conexao com o servidor. Trabalhando offline.'
      }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: {
          'Content-Type': 'application/json',
          'X-Offline': 'true'
        }
      }
    )
  }
}

// Background sync for pending readings
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-readings') {
    console.log('[SW] Background sync triggered')
    event.waitUntil(syncPendingReadings())
  }
})

async function syncPendingReadings() {
  // This will be triggered when connection is restored
  // The actual sync logic is in the React hook
  console.log('[SW] Would sync pending readings here')

  // Notify clients about sync opportunity
  const clients = await self.clients.matchAll()
  clients.forEach(client => {
    client.postMessage({
      type: 'SYNC_OPPORTUNITY',
      timestamp: Date.now()
    })
  })
}

// Handle messages from clients
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }

  if (event.data.type === 'CACHE_SESSION') {
    // Cache session data for offline use
    const { sessionId, data } = event.data
    cacheSessionData(sessionId, data)
  }
})

async function cacheSessionData(sessionId, data) {
  const cache = await caches.open(DYNAMIC_CACHE)

  // Cache session details
  const sessionUrl = `/api/inventory/sessions/${sessionId}`
  const sessionResponse = new Response(JSON.stringify(data.session), {
    headers: { 'Content-Type': 'application/json' }
  })
  await cache.put(sessionUrl, sessionResponse)

  // Cache expected assets
  if (data.expectedAssets) {
    const assetsUrl = `/api/inventory/sessions/${sessionId}/expected`
    const assetsResponse = new Response(JSON.stringify(data.expectedAssets), {
      headers: { 'Content-Type': 'application/json' }
    })
    await cache.put(assetsUrl, assetsResponse)
  }

  console.log(`[SW] Cached session ${sessionId} for offline use`)
}
