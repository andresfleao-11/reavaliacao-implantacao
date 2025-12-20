/**
 * IndexedDB Service para armazenamento offline de dados de inventário
 * Armazena: sessões, bens esperados, leituras pendentes, dados mestres
 */

const DB_NAME = 'inventory_offline_db'
const DB_VERSION = 1

// Store names
const STORES = {
  SESSIONS: 'sessions',
  EXPECTED_ASSETS: 'expected_assets',
  PENDING_READINGS: 'pending_readings',
  MASTER_DATA: 'master_data',
  SYNC_QUEUE: 'sync_queue'
} as const

export interface OfflineSession {
  id: number
  code: string
  name: string
  status: string
  project_id: number
  total_expected: number
  total_found: number
  synced_at: string
  cached_at: string
}

export interface OfflineExpectedAsset {
  id: number
  session_id: number
  asset_code: string
  description: string
  rfid_code?: string
  barcode?: string
  expected_ul_code?: string
  verified: boolean
}

export interface OfflinePendingReading {
  local_id: string
  session_id: number
  identifier: string
  read_method: string
  physical_condition?: string
  observations?: string
  read_at: string
  synced: boolean
  sync_error?: string
}

export interface SyncQueueItem {
  id: string
  type: 'reading' | 'session_complete'
  session_id: number
  data: any
  created_at: string
  attempts: number
  last_error?: string
}

class IndexedDBService {
  private db: IDBDatabase | null = null
  private dbReady: Promise<IDBDatabase> | null = null

  async init(): Promise<IDBDatabase> {
    if (this.db) return this.db
    if (this.dbReady) return this.dbReady

    this.dbReady = new Promise((resolve, reject) => {
      if (typeof window === 'undefined' || !window.indexedDB) {
        reject(new Error('IndexedDB not supported'))
        return
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onerror = () => {
        reject(request.error)
      }

      request.onsuccess = () => {
        this.db = request.result
        resolve(this.db)
      }

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result

        // Sessions store
        if (!db.objectStoreNames.contains(STORES.SESSIONS)) {
          const sessionsStore = db.createObjectStore(STORES.SESSIONS, { keyPath: 'id' })
          sessionsStore.createIndex('code', 'code', { unique: true })
          sessionsStore.createIndex('status', 'status', { unique: false })
        }

        // Expected assets store
        if (!db.objectStoreNames.contains(STORES.EXPECTED_ASSETS)) {
          const assetsStore = db.createObjectStore(STORES.EXPECTED_ASSETS, { keyPath: 'id' })
          assetsStore.createIndex('session_id', 'session_id', { unique: false })
          assetsStore.createIndex('asset_code', 'asset_code', { unique: false })
          assetsStore.createIndex('rfid_code', 'rfid_code', { unique: false })
          assetsStore.createIndex('barcode', 'barcode', { unique: false })
        }

        // Pending readings store
        if (!db.objectStoreNames.contains(STORES.PENDING_READINGS)) {
          const readingsStore = db.createObjectStore(STORES.PENDING_READINGS, { keyPath: 'local_id' })
          readingsStore.createIndex('session_id', 'session_id', { unique: false })
          readingsStore.createIndex('synced', 'synced', { unique: false })
        }

        // Master data store (UGs, ULs, physical status, etc.)
        if (!db.objectStoreNames.contains(STORES.MASTER_DATA)) {
          const masterStore = db.createObjectStore(STORES.MASTER_DATA, { keyPath: ['type', 'code'] })
          masterStore.createIndex('type', 'type', { unique: false })
        }

        // Sync queue store
        if (!db.objectStoreNames.contains(STORES.SYNC_QUEUE)) {
          const syncStore = db.createObjectStore(STORES.SYNC_QUEUE, { keyPath: 'id' })
          syncStore.createIndex('type', 'type', { unique: false })
          syncStore.createIndex('session_id', 'session_id', { unique: false })
        }
      }
    })

    return this.dbReady
  }

  // ===== Sessions =====

  async saveSession(session: OfflineSession): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.SESSIONS, 'readwrite')
      const store = transaction.objectStore(STORES.SESSIONS)
      const request = store.put(session)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  async getSession(id: number): Promise<OfflineSession | undefined> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.SESSIONS, 'readonly')
      const store = transaction.objectStore(STORES.SESSIONS)
      const request = store.get(id)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve(request.result)
    })
  }

  async getAllSessions(): Promise<OfflineSession[]> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.SESSIONS, 'readonly')
      const store = transaction.objectStore(STORES.SESSIONS)
      const request = store.getAll()
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve(request.result)
    })
  }

  // ===== Expected Assets =====

  async saveExpectedAssets(assets: OfflineExpectedAsset[]): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.EXPECTED_ASSETS, 'readwrite')
      const store = transaction.objectStore(STORES.EXPECTED_ASSETS)

      assets.forEach(asset => {
        store.put(asset)
      })

      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
    })
  }

  async getExpectedAssetsBySession(sessionId: number): Promise<OfflineExpectedAsset[]> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.EXPECTED_ASSETS, 'readonly')
      const store = transaction.objectStore(STORES.EXPECTED_ASSETS)
      const index = store.index('session_id')
      const request = index.getAll(sessionId)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve(request.result)
    })
  }

  async findExpectedAsset(sessionId: number, identifier: string): Promise<OfflineExpectedAsset | undefined> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.EXPECTED_ASSETS, 'readonly')
      const store = transaction.objectStore(STORES.EXPECTED_ASSETS)

      // Try by asset_code first
      const codeIndex = store.index('asset_code')
      const codeRequest = codeIndex.getAll(identifier)

      codeRequest.onsuccess = () => {
        const results = codeRequest.result.filter(a => a.session_id === sessionId)
        if (results.length > 0) {
          resolve(results[0])
          return
        }

        // Try by rfid_code
        const rfidIndex = store.index('rfid_code')
        const rfidRequest = rfidIndex.getAll(identifier)

        rfidRequest.onsuccess = () => {
          const rfidResults = rfidRequest.result.filter(a => a.session_id === sessionId)
          if (rfidResults.length > 0) {
            resolve(rfidResults[0])
            return
          }

          // Try by barcode
          const barcodeIndex = store.index('barcode')
          const barcodeRequest = barcodeIndex.getAll(identifier)

          barcodeRequest.onsuccess = () => {
            const barcodeResults = barcodeRequest.result.filter(a => a.session_id === sessionId)
            resolve(barcodeResults.length > 0 ? barcodeResults[0] : undefined)
          }

          barcodeRequest.onerror = () => reject(barcodeRequest.error)
        }

        rfidRequest.onerror = () => reject(rfidRequest.error)
      }

      codeRequest.onerror = () => reject(codeRequest.error)
    })
  }

  async markAssetAsVerified(id: number): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.EXPECTED_ASSETS, 'readwrite')
      const store = transaction.objectStore(STORES.EXPECTED_ASSETS)
      const getRequest = store.get(id)

      getRequest.onsuccess = () => {
        const asset = getRequest.result
        if (asset) {
          asset.verified = true
          const putRequest = store.put(asset)
          putRequest.onerror = () => reject(putRequest.error)
          putRequest.onsuccess = () => resolve()
        } else {
          resolve()
        }
      }

      getRequest.onerror = () => reject(getRequest.error)
    })
  }

  // ===== Pending Readings =====

  async savePendingReading(reading: OfflinePendingReading): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.PENDING_READINGS, 'readwrite')
      const store = transaction.objectStore(STORES.PENDING_READINGS)
      const request = store.put(reading)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  async getPendingReadingsBySession(sessionId: number): Promise<OfflinePendingReading[]> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.PENDING_READINGS, 'readonly')
      const store = transaction.objectStore(STORES.PENDING_READINGS)
      const index = store.index('session_id')
      const request = index.getAll(sessionId)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve(request.result)
    })
  }

  async getUnsyncedReadings(): Promise<OfflinePendingReading[]> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.PENDING_READINGS, 'readonly')
      const store = transaction.objectStore(STORES.PENDING_READINGS)
      const request = store.getAll()
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        // Filter unsynced readings
        const unsynced = request.result.filter((r: OfflinePendingReading) => !r.synced)
        resolve(unsynced)
      }
    })
  }

  async markReadingAsSynced(localId: string): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.PENDING_READINGS, 'readwrite')
      const store = transaction.objectStore(STORES.PENDING_READINGS)
      const getRequest = store.get(localId)

      getRequest.onsuccess = () => {
        const reading = getRequest.result
        if (reading) {
          reading.synced = true
          const putRequest = store.put(reading)
          putRequest.onerror = () => reject(putRequest.error)
          putRequest.onsuccess = () => resolve()
        } else {
          resolve()
        }
      }

      getRequest.onerror = () => reject(getRequest.error)
    })
  }

  async updateReadingSyncError(localId: string, error: string): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.PENDING_READINGS, 'readwrite')
      const store = transaction.objectStore(STORES.PENDING_READINGS)
      const getRequest = store.get(localId)

      getRequest.onsuccess = () => {
        const reading = getRequest.result
        if (reading) {
          reading.sync_error = error
          const putRequest = store.put(reading)
          putRequest.onerror = () => reject(putRequest.error)
          putRequest.onsuccess = () => resolve()
        } else {
          resolve()
        }
      }

      getRequest.onerror = () => reject(getRequest.error)
    })
  }

  // ===== Sync Queue =====

  async addToSyncQueue(item: SyncQueueItem): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.SYNC_QUEUE, 'readwrite')
      const store = transaction.objectStore(STORES.SYNC_QUEUE)
      const request = store.put(item)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  async getSyncQueue(): Promise<SyncQueueItem[]> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.SYNC_QUEUE, 'readonly')
      const store = transaction.objectStore(STORES.SYNC_QUEUE)
      const request = store.getAll()
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve(request.result)
    })
  }

  async removeFromSyncQueue(id: string): Promise<void> {
    const db = await this.init()
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORES.SYNC_QUEUE, 'readwrite')
      const store = transaction.objectStore(STORES.SYNC_QUEUE)
      const request = store.delete(id)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }

  // ===== Utility =====

  async clearSessionData(sessionId: number): Promise<void> {
    const db = await this.init()

    // Clear expected assets for session
    const assetsTransaction = db.transaction(STORES.EXPECTED_ASSETS, 'readwrite')
    const assetsStore = assetsTransaction.objectStore(STORES.EXPECTED_ASSETS)
    const assetsIndex = assetsStore.index('session_id')
    const assetsRequest = assetsIndex.getAllKeys(sessionId)

    assetsRequest.onsuccess = () => {
      assetsRequest.result.forEach(key => assetsStore.delete(key))
    }

    // Clear pending readings for session
    const readingsTransaction = db.transaction(STORES.PENDING_READINGS, 'readwrite')
    const readingsStore = readingsTransaction.objectStore(STORES.PENDING_READINGS)
    const readingsIndex = readingsStore.index('session_id')
    const readingsRequest = readingsIndex.getAllKeys(sessionId)

    readingsRequest.onsuccess = () => {
      readingsRequest.result.forEach(key => readingsStore.delete(key))
    }
  }

  async getOfflineStatistics(sessionId: number): Promise<{
    total_expected: number
    total_verified: number
    pending_sync: number
  }> {
    const assets = await this.getExpectedAssetsBySession(sessionId)
    const readings = await this.getPendingReadingsBySession(sessionId)

    const unsyncedReadings = readings.filter(r => !r.synced)
    const verifiedAssets = assets.filter(a => a.verified)

    return {
      total_expected: assets.length,
      total_verified: verifiedAssets.length,
      pending_sync: unsyncedReadings.length
    }
  }
}

// Singleton instance
export const offlineDB = new IndexedDBService()

// Helper to generate local IDs
export function generateLocalId(): string {
  return `local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}
