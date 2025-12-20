'use client'

import { useState, useEffect, useCallback } from 'react'
import { offlineDB, OfflinePendingReading, generateLocalId } from '@/lib/indexeddb'
import { inventorySessionsApi } from '@/lib/api'

export type ConnectionStatus = 'online' | 'offline' | 'syncing'
export type SyncStatus = 'synced' | 'pending' | 'error'

interface UseOnlineStatusReturn {
  isOnline: boolean
  connectionStatus: ConnectionStatus
  syncStatus: SyncStatus
  pendingCount: number
  lastSyncAt: Date | null
  syncNow: () => Promise<void>
  isSyncing: boolean
  syncError: string | null
}

export function useOnlineStatus(): UseOnlineStatusReturn {
  const [isOnline, setIsOnline] = useState(true)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('online')
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('synced')
  const [pendingCount, setPendingCount] = useState(0)
  const [lastSyncAt, setLastSyncAt] = useState<Date | null>(null)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)

  // Check for pending readings
  const checkPendingReadings = useCallback(async () => {
    try {
      const unsynced = await offlineDB.getUnsyncedReadings()
      setPendingCount(unsynced.length)
      setSyncStatus(unsynced.length > 0 ? 'pending' : 'synced')
    } catch (err) {
      console.error('Error checking pending readings:', err)
    }
  }, [])

  // Sync pending readings to server
  const syncNow = useCallback(async () => {
    if (isSyncing || !isOnline) return

    setIsSyncing(true)
    setConnectionStatus('syncing')
    setSyncError(null)

    try {
      const unsyncedReadings = await offlineDB.getUnsyncedReadings()

      if (unsyncedReadings.length === 0) {
        setSyncStatus('synced')
        setLastSyncAt(new Date())
        return
      }

      let successCount = 0
      let errorCount = 0

      for (const reading of unsyncedReadings) {
        try {
          // Send to server
          await inventorySessionsApi.registerReading(reading.session_id, {
            identifier: reading.identifier,
            read_method: reading.read_method,
            physical_condition: reading.physical_condition,
            observations: reading.observations
          })

          // Mark as synced
          await offlineDB.markReadingAsSynced(reading.local_id)
          successCount++
        } catch (err: any) {
          errorCount++
          await offlineDB.updateReadingSyncError(
            reading.local_id,
            err.response?.data?.detail || err.message || 'Sync failed'
          )
        }
      }

      // Update counts
      await checkPendingReadings()

      if (errorCount > 0) {
        setSyncError(`${errorCount} leitura(s) falharam na sincronização`)
        setSyncStatus('error')
      } else {
        setSyncStatus('synced')
      }

      setLastSyncAt(new Date())
    } catch (err: any) {
      setSyncError(err.message || 'Erro na sincronização')
      setSyncStatus('error')
    } finally {
      setIsSyncing(false)
      setConnectionStatus(isOnline ? 'online' : 'offline')
    }
  }, [isOnline, isSyncing, checkPendingReadings])

  // Handle online/offline events
  useEffect(() => {
    if (typeof window === 'undefined') return

    const handleOnline = () => {
      setIsOnline(true)
      setConnectionStatus('online')
      // Auto sync when coming back online
      syncNow()
    }

    const handleOffline = () => {
      setIsOnline(false)
      setConnectionStatus('offline')
    }

    // Initial state
    setIsOnline(navigator.onLine)
    setConnectionStatus(navigator.onLine ? 'online' : 'offline')

    // Check pending on mount
    checkPendingReadings()

    // Listen for changes
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [syncNow, checkPendingReadings])

  // Periodic check for pending readings
  useEffect(() => {
    const interval = setInterval(checkPendingReadings, 10000) // Every 10 seconds
    return () => clearInterval(interval)
  }, [checkPendingReadings])

  // Auto sync every 30 seconds when online and have pending
  useEffect(() => {
    if (!isOnline || pendingCount === 0) return

    const interval = setInterval(() => {
      syncNow()
    }, 30000) // Every 30 seconds

    return () => clearInterval(interval)
  }, [isOnline, pendingCount, syncNow])

  return {
    isOnline,
    connectionStatus,
    syncStatus,
    pendingCount,
    lastSyncAt,
    syncNow,
    isSyncing,
    syncError
  }
}

// Hook for offline reading management
export function useOfflineReading(sessionId: number) {
  const { isOnline, syncNow } = useOnlineStatus()

  const saveReadingOffline = useCallback(async (data: {
    identifier: string
    read_method: string
    physical_condition?: string
    observations?: string
  }): Promise<{ success: boolean; local_id: string; category: string }> => {
    const localId = generateLocalId()

    // Find expected asset in local DB
    const expectedAsset = await offlineDB.findExpectedAsset(sessionId, data.identifier)
    const category = expectedAsset ? 'found' : 'unregistered'

    const reading: OfflinePendingReading = {
      local_id: localId,
      session_id: sessionId,
      identifier: data.identifier,
      read_method: data.read_method,
      physical_condition: data.physical_condition,
      observations: data.observations,
      read_at: new Date().toISOString(),
      synced: false
    }

    await offlineDB.savePendingReading(reading)

    // Mark asset as verified if found
    if (expectedAsset) {
      await offlineDB.markAssetAsVerified(expectedAsset.id)
    }

    // If online, try to sync immediately
    if (isOnline) {
      try {
        await syncNow()
      } catch (err) {
        // Ignore - will sync later
      }
    }

    return { success: true, local_id: localId, category }
  }, [sessionId, isOnline, syncNow])

  const getOfflineStats = useCallback(async () => {
    return offlineDB.getOfflineStatistics(sessionId)
  }, [sessionId])

  return {
    saveReadingOffline,
    getOfflineStats,
    isOnline
  }
}
