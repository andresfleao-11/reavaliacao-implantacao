'use client'

import { useOnlineStatus, ConnectionStatus, SyncStatus } from '@/hooks/useOnlineStatus'

interface ConnectionStatusIndicatorProps {
  showDetails?: boolean
  className?: string
}

export function ConnectionStatusIndicator({
  showDetails = false,
  className = ''
}: ConnectionStatusIndicatorProps) {
  const {
    isOnline,
    connectionStatus,
    syncStatus,
    pendingCount,
    lastSyncAt,
    syncNow,
    isSyncing,
    syncError
  } = useOnlineStatus()

  const getStatusColor = (): string => {
    if (connectionStatus === 'offline') return 'bg-red-500'
    if (connectionStatus === 'syncing') return 'bg-yellow-500 animate-pulse'
    if (syncStatus === 'pending') return 'bg-yellow-500'
    if (syncStatus === 'error') return 'bg-orange-500'
    return 'bg-green-500'
  }

  const getStatusText = (): string => {
    if (connectionStatus === 'offline') return 'Offline'
    if (connectionStatus === 'syncing') return 'Sincronizando...'
    if (syncStatus === 'pending') return `${pendingCount} pendente(s)`
    if (syncStatus === 'error') return 'Erro na sync'
    return 'Online'
  }

  const getStatusIcon = (): React.ReactNode => {
    if (connectionStatus === 'offline') {
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414" />
        </svg>
      )
    }

    if (connectionStatus === 'syncing') {
      return (
        <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      )
    }

    if (syncStatus === 'pending' || syncStatus === 'error') {
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    }

    return (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
      </svg>
    )
  }

  if (!showDetails) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
        <span className="text-xs text-gray-600 dark:text-gray-400">{getStatusText()}</span>
      </div>
    )
  }

  return (
    <div className={`p-3 rounded-lg border ${
      connectionStatus === 'offline'
        ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        : syncStatus === 'pending' || syncStatus === 'error'
        ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
        : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
    } ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
          <div className="flex items-center gap-1">
            {getStatusIcon()}
            <span className={`text-sm font-medium ${
              connectionStatus === 'offline'
                ? 'text-red-700 dark:text-red-400'
                : syncStatus === 'pending' || syncStatus === 'error'
                ? 'text-yellow-700 dark:text-yellow-400'
                : 'text-green-700 dark:text-green-400'
            }`}>
              {getStatusText()}
            </span>
          </div>
        </div>

        {isOnline && pendingCount > 0 && !isSyncing && (
          <button
            onClick={syncNow}
            className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Sincronizar
          </button>
        )}
      </div>

      {syncError && (
        <p className="text-xs text-red-600 dark:text-red-400 mt-1">{syncError}</p>
      )}

      {lastSyncAt && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Sincronizado: {lastSyncAt.toLocaleTimeString('pt-BR')}
        </p>
      )}
    </div>
  )
}

// Compact version for header/sidebar
export function ConnectionStatusBadge() {
  const { connectionStatus, syncStatus, pendingCount } = useOnlineStatus()

  const getColor = (): string => {
    if (connectionStatus === 'offline') return 'text-red-500'
    if (connectionStatus === 'syncing') return 'text-yellow-500'
    if (syncStatus === 'pending') return 'text-yellow-500'
    if (syncStatus === 'error') return 'text-orange-500'
    return 'text-green-500'
  }

  return (
    <div className={`flex items-center gap-1 ${getColor()}`}>
      <div className={`w-2 h-2 rounded-full ${
        connectionStatus === 'offline' ? 'bg-red-500' :
        connectionStatus === 'syncing' ? 'bg-yellow-500 animate-pulse' :
        syncStatus === 'pending' ? 'bg-yellow-500' :
        syncStatus === 'error' ? 'bg-orange-500' :
        'bg-green-500'
      }`} />
      {pendingCount > 0 && (
        <span className="text-xs font-medium">{pendingCount}</span>
      )}
    </div>
  )
}
