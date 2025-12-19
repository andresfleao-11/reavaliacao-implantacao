package com.reavaliacao.rfidmiddleware.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reavaliacao.rfidmiddleware.data.AppSettings
import com.reavaliacao.rfidmiddleware.data.SettingsDataStore
import com.reavaliacao.rfidmiddleware.data.repository.TagRepository
import com.reavaliacao.rfidmiddleware.rfid.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

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
    val errorMessage: String? = null,
    val deviceInfo: DeviceInfo = DeviceInfo(),
    val readMode: ReadMode = ReadMode.RFID
)

sealed class SyncStatus {
    object Idle : SyncStatus()
    object Syncing : SyncStatus()
    data class Success(val count: Int) : SyncStatus()
    data class Error(val message: String) : SyncStatus()
}

@HiltViewModel
class MainViewModel @Inject constructor(
    private val rfidManager: RfidManager,
    private val tagRepository: TagRepository,
    private val settingsDataStore: SettingsDataStore
) : ViewModel() {

    companion object {
        private const val TAG = "MainViewModel"
    }

    private val _uiState = MutableStateFlow(MainUiState())
    val uiState: StateFlow<MainUiState> = _uiState.asStateFlow()

    private var currentBatchId: String = UUID.randomUUID().toString()

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

        android.util.Log.d(TAG, "MainViewModel init completed")
    }

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

    fun clearError() {
        _uiState.update { it.copy(errorMessage = null, syncStatus = SyncStatus.Idle) }
    }

    override fun onCleared() {
        super.onCleared()
        rfidManager.release()
    }
}
