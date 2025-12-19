package com.reavaliacao.rfidmiddleware.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reavaliacao.rfidmiddleware.data.AppSettings
import com.reavaliacao.rfidmiddleware.data.SettingsDataStore
import com.reavaliacao.rfidmiddleware.data.remote.ActiveSessionResponse
import com.reavaliacao.rfidmiddleware.data.repository.TagRepository
import com.reavaliacao.rfidmiddleware.rfid.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

data class ActiveSession(
    val sessionId: Int,
    val readingType: String,  // "RFID" ou "BARCODE"
    val projectId: Int? = null,
    val location: String? = null,
    val expiresAt: String? = null
)

data class MainUiState(
    val connectionState: ConnectionState = ConnectionState.Disconnected,
    val isScanning: Boolean = false,
    val isReading: Boolean = false,
    val scannedDevices: List<BleDevice> = emptyList(),
    val readTags: List<RfidTag> = emptyList(),
    val barcodeResults: List<BarcodeResult> = emptyList(),
    val unsyncedCount: Int = 0,
    val settings: AppSettings = AppSettings(),
    val syncStatus: SyncStatus = SyncStatus.Idle,
    val connectionTestStatus: ConnectionTestStatus = ConnectionTestStatus.Idle,
    val errorMessage: String? = null,
    val deviceInfo: DeviceInfo = DeviceInfo(),
    val readMode: ReadMode = ReadMode.RFID,
    // Session state
    val activeSession: ActiveSession? = null,
    val sessionStatus: SessionCheckStatus = SessionCheckStatus.Idle,
    val sessionSendStatus: SessionSendStatus = SessionSendStatus.Idle
)

sealed class SyncStatus {
    object Idle : SyncStatus()
    object Syncing : SyncStatus()
    data class Success(val count: Int) : SyncStatus()
    data class Error(val message: String) : SyncStatus()
}

sealed class ConnectionTestStatus {
    object Idle : ConnectionTestStatus()
    object Testing : ConnectionTestStatus()
    data class Success(val message: String) : ConnectionTestStatus()
    data class Error(val message: String) : ConnectionTestStatus()
}

sealed class SessionCheckStatus {
    object Idle : SessionCheckStatus()
    object Checking : SessionCheckStatus()
    object NoSession : SessionCheckStatus()
    data class HasSession(val type: String) : SessionCheckStatus()
    data class Error(val message: String) : SessionCheckStatus()
}

sealed class SessionSendStatus {
    object Idle : SessionSendStatus()
    object Sending : SessionSendStatus()
    data class Success(val addedCount: Int, val totalCount: Int) : SessionSendStatus()
    data class Error(val message: String) : SessionSendStatus()
}

@HiltViewModel
class MainViewModel @Inject constructor(
    private val rfidManager: RfidManager,
    private val tagRepository: TagRepository,
    private val settingsDataStore: SettingsDataStore
) : ViewModel() {

    companion object {
        private const val TAG = "MainViewModel"
        private const val SESSION_POLL_INTERVAL = 3000L // 3 segundos
    }

    private val _uiState = MutableStateFlow(MainUiState())
    val uiState: StateFlow<MainUiState> = _uiState.asStateFlow()

    private var currentBatchId: String = UUID.randomUUID().toString()
    private var sessionPollJob: Job? = null

    init {
        android.util.Log.d(TAG, "MainViewModel init started")
        try {
            rfidManager.initialize()
            android.util.Log.d(TAG, "RfidManager initialized")
        } catch (e: Exception) {
            android.util.Log.e(TAG, "Error initializing RfidManager", e)
        }

        // Collect connection state
        viewModelScope.launch {
            rfidManager.connectionState.collect { state ->
                _uiState.update { it.copy(connectionState = state) }
            }
        }

        // Collect scanning state
        viewModelScope.launch {
            rfidManager.isScanning.collect { scanning ->
                _uiState.update { it.copy(isScanning = scanning) }
            }
        }

        // Collect reading state
        viewModelScope.launch {
            rfidManager.isReading.collect { reading ->
                _uiState.update { it.copy(isReading = reading) }
            }
        }

        // Collect scanned devices
        viewModelScope.launch {
            rfidManager.scannedDevices.collect { devices ->
                _uiState.update { it.copy(scannedDevices = devices) }
            }
        }

        // Collect read tags
        viewModelScope.launch {
            rfidManager.readTags.collect { tags ->
                _uiState.update { it.copy(readTags = tags) }
            }
        }

        // Collect barcode results
        viewModelScope.launch {
            rfidManager.barcodeResults.collect { barcodes ->
                _uiState.update { it.copy(barcodeResults = barcodes) }
            }
        }

        // Collect device info (battery, power, etc)
        viewModelScope.launch {
            rfidManager.deviceInfo.collect { info ->
                _uiState.update { it.copy(deviceInfo = info) }
            }
        }

        // Collect read mode
        viewModelScope.launch {
            rfidManager.readMode.collect { mode ->
                _uiState.update { it.copy(readMode = mode) }
            }
        }

        // Collect settings
        viewModelScope.launch {
            settingsDataStore.settings.collect { settings ->
                _uiState.update { it.copy(settings = settings) }
                // Apply power setting when connected
                if (_uiState.value.connectionState is ConnectionState.Connected) {
                    rfidManager.setPower(settings.readerPower)
                }
            }
        }

        // Collect unsynced count
        viewModelScope.launch {
            tagRepository.getUnsyncedCount().collect { count ->
                _uiState.update { it.copy(unsyncedCount = count) }
            }
        }

        // Start session polling
        startSessionPolling()

        android.util.Log.d(TAG, "MainViewModel init completed")
    }

    // ==================== Session Management ====================

    private fun startSessionPolling() {
        sessionPollJob?.cancel()
        sessionPollJob = viewModelScope.launch {
            while (true) {
                checkActiveSession()
                delay(SESSION_POLL_INTERVAL)
            }
        }
    }

    fun checkActiveSession() {
        viewModelScope.launch {
            val settings = _uiState.value.settings
            if (settings.serverUrl.isBlank()) {
                android.util.Log.d(TAG, "checkActiveSession: Server URL not configured")
                return@launch
            }

            // Precisamos do user_id do token JWT
            // Por simplicidade, vamos extrair do token (formato: header.payload.signature)
            val userId = extractUserIdFromToken(settings.authToken)
            if (userId == null) {
                android.util.Log.d(TAG, "checkActiveSession: Could not extract user_id from token")
                _uiState.update { it.copy(sessionStatus = SessionCheckStatus.NoSession, activeSession = null) }
                return@launch
            }

            android.util.Log.d(TAG, "checkActiveSession: Checking for user $userId")

            val result = tagRepository.checkActiveSession(userId)
            result.fold(
                onSuccess = { response ->
                    android.util.Log.d(TAG, "checkActiveSession: has_active_session=${response.has_active_session}, type=${response.reading_type}")
                    if (response.has_active_session && response.session_id != null) {
                        val session = ActiveSession(
                            sessionId = response.session_id,
                            readingType = response.reading_type ?: "RFID",
                            projectId = response.project_id,
                            location = response.location,
                            expiresAt = response.expires_at
                        )
                        _uiState.update {
                            it.copy(
                                activeSession = session,
                                sessionStatus = SessionCheckStatus.HasSession(response.reading_type ?: "RFID")
                            )
                        }
                    } else {
                        _uiState.update {
                            it.copy(
                                activeSession = null,
                                sessionStatus = SessionCheckStatus.NoSession
                            )
                        }
                    }
                },
                onFailure = { error ->
                    android.util.Log.e(TAG, "checkActiveSession: Error - ${error.message}")
                    // Don't update to error state, just log - polling will retry
                }
            )
        }
    }

    private fun extractUserIdFromToken(token: String): Int? {
        if (token.isBlank()) return null

        try {
            // JWT format: header.payload.signature
            val parts = token.split(".")
            if (parts.size != 3) return null

            // Decode payload (base64)
            val payload = parts[1]
            val decodedBytes = android.util.Base64.decode(payload, android.util.Base64.URL_SAFE)
            val decodedPayload = String(decodedBytes)

            android.util.Log.d(TAG, "JWT Payload: $decodedPayload")

            // Parse JSON manually (simples, sem biblioteca adicional)
            // Formato esperado: {"sub":"1","exp":...}
            val subPattern = """"sub"\s*:\s*"?(\d+)"?""".toRegex()
            val match = subPattern.find(decodedPayload)
            return match?.groupValues?.get(1)?.toIntOrNull()
        } catch (e: Exception) {
            android.util.Log.e(TAG, "Error extracting user_id from token", e)
            return null
        }
    }

    fun sendReadingsToSession() {
        viewModelScope.launch {
            val session = _uiState.value.activeSession
            if (session == null) {
                _uiState.update {
                    it.copy(sessionSendStatus = SessionSendStatus.Error("Nenhuma sessao ativa"))
                }
                return@launch
            }

            val tags = _uiState.value.readTags
            val barcodes = _uiState.value.barcodeResults

            // Coletar as leituras corretas baseado no tipo de sessão
            val readings = when (session.readingType) {
                "RFID" -> tags.map { tag ->
                    com.reavaliacao.rfidmiddleware.data.remote.SessionReadingRequest(
                        code = tag.epc,
                        rssi = tag.rssi,
                        device_id = when (val state = _uiState.value.connectionState) {
                            is ConnectionState.Connected -> "R6-${state.deviceAddress}"
                            else -> "R6-Unknown"
                        }
                    )
                }
                "BARCODE" -> barcodes.map { barcode ->
                    com.reavaliacao.rfidmiddleware.data.remote.SessionReadingRequest(
                        code = barcode.code,
                        rssi = null,
                        device_id = when (val state = _uiState.value.connectionState) {
                            is ConnectionState.Connected -> "R6-${state.deviceAddress}"
                            else -> "R6-Unknown"
                        }
                    )
                }
                else -> emptyList()
            }

            if (readings.isEmpty()) {
                _uiState.update {
                    it.copy(sessionSendStatus = SessionSendStatus.Error("Nenhuma leitura para enviar"))
                }
                return@launch
            }

            android.util.Log.d(TAG, "sendReadingsToSession: Sending ${readings.size} readings to session ${session.sessionId}")
            _uiState.update { it.copy(sessionSendStatus = SessionSendStatus.Sending) }

            val result = tagRepository.sendSessionReadings(session.sessionId, readings)
            result.fold(
                onSuccess = { response ->
                    android.util.Log.d(TAG, "sendReadingsToSession: Success - added=${response.added_count}, total=${response.total_count}")
                    _uiState.update {
                        it.copy(sessionSendStatus = SessionSendStatus.Success(response.added_count, response.total_count))
                    }
                    // Limpar as leituras após enviar com sucesso
                    if (session.readingType == "RFID") {
                        rfidManager.clearTags()
                    } else {
                        rfidManager.clearBarcodes()
                    }
                },
                onFailure = { error ->
                    android.util.Log.e(TAG, "sendReadingsToSession: Error - ${error.message}")
                    _uiState.update {
                        it.copy(sessionSendStatus = SessionSendStatus.Error(error.message ?: "Erro ao enviar"))
                    }
                }
            )
        }
    }

    fun clearSessionSendStatus() {
        _uiState.update { it.copy(sessionSendStatus = SessionSendStatus.Idle) }
    }

    // ==================== Device Scanning ====================

    fun startScanDevices() {
        rfidManager.startScanDevices()
    }

    fun stopScanDevices() {
        rfidManager.stopScanDevices()
    }

    fun connectToDevice(address: String) {
        rfidManager.connect(address)
        viewModelScope.launch {
            settingsDataStore.updateLastConnectedDevice(address)
        }
    }

    fun disconnect() {
        rfidManager.disconnect()
    }

    // ==================== Read Mode ====================

    fun setReadMode(mode: ReadMode) {
        rfidManager.setReadMode(mode)
    }

    // ==================== RFID ====================

    fun startReading() {
        currentBatchId = UUID.randomUUID().toString()
        when (_uiState.value.readMode) {
            ReadMode.RFID -> rfidManager.startReading()
            ReadMode.BARCODE -> rfidManager.startBarcodeReading()
        }
    }

    fun stopReading() {
        when (_uiState.value.readMode) {
            ReadMode.RFID -> rfidManager.stopReading()
            ReadMode.BARCODE -> rfidManager.stopBarcodeReading()
        }
    }

    fun clearTags() {
        rfidManager.clearTags()
    }

    // ==================== Barcode ====================

    fun startBarcodeReading() {
        rfidManager.startBarcodeReading()
    }

    fun stopBarcodeReading() {
        rfidManager.stopBarcodeReading()
    }

    fun clearBarcodes() {
        rfidManager.clearBarcodes()
    }

    // ==================== Data Management ====================

    fun saveTagsLocally() {
        viewModelScope.launch {
            val tags = _uiState.value.readTags
            val barcodes = _uiState.value.barcodeResults
            val deviceAddress = when (val state = _uiState.value.connectionState) {
                is ConnectionState.Connected -> state.deviceAddress
                else -> ""
            }

            // Salvar tags RFID
            if (tags.isNotEmpty()) {
                tagRepository.saveTags(tags, deviceAddress, currentBatchId)
                rfidManager.clearTags()
            }

            // Salvar barcodes como tags (usando EPC para codigo)
            if (barcodes.isNotEmpty()) {
                val barcodeTags = barcodes.map { barcode ->
                    RfidTag(
                        epc = barcode.code,
                        rssi = "BARCODE",
                        timestamp = barcode.timestamp
                    )
                }
                tagRepository.saveTags(barcodeTags, deviceAddress, "$currentBatchId-BC")
                rfidManager.clearBarcodes()
            }
        }
    }

    fun clearAll() {
        rfidManager.clearTags()
        rfidManager.clearBarcodes()
    }

    fun syncTags() {
        viewModelScope.launch {
            val settings = _uiState.value.settings
            if (settings.serverUrl.isBlank() || settings.authToken.isBlank()) {
                _uiState.update {
                    it.copy(
                        syncStatus = SyncStatus.Error("Configure URL e Token nas configuracoes"),
                        errorMessage = "Configure URL e Token nas configuracoes"
                    )
                }
                return@launch
            }

            _uiState.update { it.copy(syncStatus = SyncStatus.Syncing) }

            val deviceId = when (val state = _uiState.value.connectionState) {
                is ConnectionState.Connected -> "R6-${state.deviceAddress}"
                else -> "R6-Unknown"
            }

            val result = tagRepository.syncTags(settings.authToken, deviceId)

            result.fold(
                onSuccess = { count ->
                    _uiState.update {
                        it.copy(
                            syncStatus = SyncStatus.Success(count),
                            errorMessage = null
                        )
                    }
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(
                            syncStatus = SyncStatus.Error(error.message ?: "Erro ao sincronizar"),
                            errorMessage = error.message
                        )
                    }
                }
            )
        }
    }

    // ==================== Settings ====================

    fun updateServerUrl(url: String) {
        viewModelScope.launch {
            settingsDataStore.updateServerUrl(url)
        }
    }

    fun updateAuthToken(token: String) {
        viewModelScope.launch {
            settingsDataStore.updateAuthToken(token)
        }
    }

    fun updateReaderPower(power: Int) {
        viewModelScope.launch {
            settingsDataStore.updateReaderPower(power)
            rfidManager.setPower(power)
        }
    }

    fun updateAutoSend(enabled: Boolean) {
        viewModelScope.launch {
            settingsDataStore.updateAutoSend(enabled)
        }
    }

    fun testConnection() {
        viewModelScope.launch {
            val settings = _uiState.value.settings
            if (settings.serverUrl.isBlank()) {
                _uiState.update {
                    it.copy(
                        connectionTestStatus = ConnectionTestStatus.Error("Configure a URL do servidor")
                    )
                }
                return@launch
            }

            _uiState.update { it.copy(connectionTestStatus = ConnectionTestStatus.Testing) }

            val result = tagRepository.testConnection()

            result.fold(
                onSuccess = { status ->
                    _uiState.update {
                        it.copy(connectionTestStatus = ConnectionTestStatus.Success("Conectado! Status: $status"))
                    }
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(connectionTestStatus = ConnectionTestStatus.Error(error.message ?: "Erro desconhecido"))
                    }
                }
            )
        }
    }

    fun clearConnectionTestStatus() {
        _uiState.update { it.copy(connectionTestStatus = ConnectionTestStatus.Idle) }
    }

    fun clearError() {
        _uiState.update { it.copy(errorMessage = null, syncStatus = SyncStatus.Idle) }
    }

    override fun onCleared() {
        super.onCleared()
        sessionPollJob?.cancel()
        rfidManager.release()
    }
}
