package com.reavaliacao.rfidmiddleware.rfid

import android.bluetooth.BluetoothDevice
import android.content.Context
import android.util.Log
import com.rscja.deviceapi.RFIDWithUHFBLE
import com.rscja.deviceapi.entity.UHFTAGInfo
import com.rscja.deviceapi.interfaces.ConnectionStatus
import com.rscja.deviceapi.interfaces.ConnectionStatusCallback
import com.rscja.deviceapi.interfaces.KeyEventCallback
import com.rscja.deviceapi.interfaces.ScanBTCallback
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

data class RfidTag(
    val epc: String,
    val rssi: String,
    val timestamp: Long = System.currentTimeMillis()
)

data class BarcodeResult(
    val code: String,
    val type: String = "BARCODE",
    val timestamp: Long = System.currentTimeMillis()
)

data class BleDevice(
    val name: String?,
    val address: String,
    val rssi: Int
)

data class DeviceInfo(
    val batteryLevel: Int = -1,
    val currentPower: Int = 20,
    val firmwareVersion: String = "",
    val isCharging: Boolean = false
)

sealed class ConnectionState {
    object Disconnected : ConnectionState()
    object Connecting : ConnectionState()
    data class Connected(val deviceName: String, val deviceAddress: String) : ConnectionState()
}

enum class ReadMode {
    RFID,
    BARCODE
}

@Singleton
class RfidManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val TAG = "RfidManager"
    }

    private val uhf: RFIDWithUHFBLE = RFIDWithUHFBLE.getInstance()

    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _isScanning = MutableStateFlow(false)
    val isScanning: StateFlow<Boolean> = _isScanning.asStateFlow()

    private val _isReading = MutableStateFlow(false)
    val isReading: StateFlow<Boolean> = _isReading.asStateFlow()

    private val _scannedDevices = MutableStateFlow<List<BleDevice>>(emptyList())
    val scannedDevices: StateFlow<List<BleDevice>> = _scannedDevices.asStateFlow()

    private val _readTags = MutableStateFlow<List<RfidTag>>(emptyList())
    val readTags: StateFlow<List<RfidTag>> = _readTags.asStateFlow()

    private val _barcodeResults = MutableStateFlow<List<BarcodeResult>>(emptyList())
    val barcodeResults: StateFlow<List<BarcodeResult>> = _barcodeResults.asStateFlow()

    private val _deviceInfo = MutableStateFlow(DeviceInfo())
    val deviceInfo: StateFlow<DeviceInfo> = _deviceInfo.asStateFlow()

    private val _readMode = MutableStateFlow(ReadMode.RFID)
    val readMode: StateFlow<ReadMode> = _readMode.asStateFlow()

    private var readingThread: Thread? = null
    private var barcodeThread: Thread? = null
    private var batteryMonitorThread: Thread? = null
    private var connectedDeviceName: String = ""
    private var connectedDeviceAddress: String = ""

    // Callback para scan de dispositivos BLE
    private val scanCallback = object : ScanBTCallback {
        override fun getDevices(device: BluetoothDevice?, rssi: Int, scanRecord: ByteArray?) {
            device?.let {
                val bleDevice = BleDevice(
                    name = it.name,
                    address = it.address,
                    rssi = rssi
                )
                val currentDevices = _scannedDevices.value.toMutableList()
                if (currentDevices.none { d -> d.address == bleDevice.address }) {
                    currentDevices.add(bleDevice)
                    _scannedDevices.value = currentDevices
                    Log.d(TAG, "Device found: ${bleDevice.name} - ${bleDevice.address}")
                }
            }
        }
    }

    // Callback para status de conexao
    private val connectionCallback = object : ConnectionStatusCallback<Any> {
        override fun getStatus(status: ConnectionStatus?, device: Any?) {
            when (status) {
                ConnectionStatus.CONNECTED -> {
                    val btDevice = device as? BluetoothDevice
                    connectedDeviceName = btDevice?.name ?: "Unknown"
                    connectedDeviceAddress = btDevice?.address ?: ""
                    _connectionState.value = ConnectionState.Connected(
                        deviceName = connectedDeviceName,
                        deviceAddress = connectedDeviceAddress
                    )
                    Log.d(TAG, "Connected to: $connectedDeviceName")

                    // Iniciar monitoramento de bateria
                    startBatteryMonitor()

                    // Obter informacoes iniciais do dispositivo
                    updateDeviceInfo()
                }
                ConnectionStatus.DISCONNECTED -> {
                    _connectionState.value = ConnectionState.Disconnected
                    _isReading.value = false
                    stopBatteryMonitor()
                    Log.d(TAG, "Disconnected")
                }
                else -> {}
            }
        }
    }

    fun initialize() {
        try {
            uhf.init(context)
            Log.d(TAG, "SDK initialized")

            // Configura callback do botao fisico do coletor
            uhf.setKeyEventCallback(object : KeyEventCallback {
                override fun onKeyDown(keyCode: Int) {
                    Log.d(TAG, "Key down: $keyCode")
                    if (uhf.connectStatus == ConnectionStatus.CONNECTED) {
                        if (!_isReading.value) {
                            when (_readMode.value) {
                                ReadMode.RFID -> startReading()
                                ReadMode.BARCODE -> startBarcodeReading()
                            }
                        }
                    }
                }

                override fun onKeyUp(keyCode: Int) {
                    Log.d(TAG, "Key up: $keyCode")
                    when (_readMode.value) {
                        ReadMode.RFID -> stopReading()
                        ReadMode.BARCODE -> stopBarcodeReading()
                    }
                }
            })
        } catch (e: Exception) {
            Log.e(TAG, "Error initializing SDK", e)
        }
    }

    fun setReadMode(mode: ReadMode) {
        if (_isReading.value) {
            // Parar leitura atual antes de trocar modo
            when (_readMode.value) {
                ReadMode.RFID -> stopReading()
                ReadMode.BARCODE -> stopBarcodeReading()
            }
        }
        _readMode.value = mode
        Log.d(TAG, "Read mode changed to: $mode")
    }

    fun startScanDevices() {
        try {
            _scannedDevices.value = emptyList()
            _isScanning.value = true
            uhf.startScanBTDevices(scanCallback)
            Log.d(TAG, "Started scanning BLE devices")
        } catch (e: Exception) {
            Log.e(TAG, "Error starting scan", e)
            _isScanning.value = false
        }
    }

    fun stopScanDevices() {
        try {
            uhf.stopScanBTDevices()
            _isScanning.value = false
            Log.d(TAG, "Stopped scanning BLE devices")
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping scan", e)
        }
    }

    fun connect(address: String) {
        try {
            _connectionState.value = ConnectionState.Connecting
            uhf.connect(address, connectionCallback)
            Log.d(TAG, "Connecting to: $address")
        } catch (e: Exception) {
            Log.e(TAG, "Error connecting", e)
            _connectionState.value = ConnectionState.Disconnected
        }
    }

    fun disconnect() {
        try {
            stopReading()
            stopBarcodeReading()
            stopBatteryMonitor()
            uhf.disconnect()
            _connectionState.value = ConnectionState.Disconnected
            Log.d(TAG, "Disconnected")
        } catch (e: Exception) {
            Log.e(TAG, "Error disconnecting", e)
        }
    }

    // ==================== RFID Reading ====================

    fun startReading() {
        if (_isReading.value) return
        if (uhf.connectStatus != ConnectionStatus.CONNECTED) {
            Log.w(TAG, "Cannot read: not connected")
            return
        }

        _isReading.value = true
        readingThread = Thread {
            try {
                if (uhf.startInventoryTag()) {
                    Log.d(TAG, "Started inventory")
                    while (_isReading.value) {
                        val tags = uhf.readTagFromBufferList()
                        if (tags != null && tags.isNotEmpty()) {
                            processTags(tags)
                        }
                        Thread.sleep(50)
                    }
                    uhf.stopInventory()
                    Log.d(TAG, "Stopped inventory")
                } else {
                    Log.e(TAG, "Failed to start inventory")
                    _isReading.value = false
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error during reading", e)
                _isReading.value = false
            }
        }
        readingThread?.start()
    }

    fun stopReading() {
        _isReading.value = false
        readingThread?.interrupt()
        readingThread = null
        try {
            uhf.stopInventory()
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping inventory", e)
        }
    }

    private fun processTags(tags: List<UHFTAGInfo>) {
        val currentTags = _readTags.value.toMutableList()
        tags.forEach { tag ->
            val rfidTag = RfidTag(
                epc = tag.epc ?: "",
                rssi = tag.rssi ?: ""
            )
            if (currentTags.none { it.epc == rfidTag.epc }) {
                currentTags.add(rfidTag)
                Log.d(TAG, "New tag: ${rfidTag.epc}")
            }
        }
        _readTags.value = currentTags
    }

    fun clearTags() {
        _readTags.value = emptyList()
    }

    // ==================== Barcode Reading ====================
    // Nota: O scanner de barcode no R6 Pro pode precisar de SDK separado
    // Por enquanto, barcode sera tratado como entrada manual ou via camera do Android

    fun startBarcodeReading() {
        if (_isReading.value) return
        if (uhf.connectStatus != ConnectionStatus.CONNECTED) {
            Log.w(TAG, "Cannot read barcode: not connected")
            return
        }

        _isReading.value = true
        barcodeThread = Thread {
            try {
                Log.d(TAG, "Starting barcode scan - usando modo manual")
                // O R6 Pro pode usar intent para capturar barcode
                // ou o usuario pode digitar manualmente
                // Implementacao depende do SDK especifico de barcode
                Thread.sleep(100)
                _isReading.value = false
                Log.d(TAG, "Barcode scan mode ready")
            } catch (e: Exception) {
                Log.e(TAG, "Error during barcode reading", e)
                _isReading.value = false
            }
        }
        barcodeThread?.start()
    }

    fun stopBarcodeReading() {
        _isReading.value = false
        barcodeThread?.interrupt()
        barcodeThread = null
        Log.d(TAG, "Barcode scan stopped")
    }

    // Adicionar barcode manualmente (via input ou camera do Android)
    fun addBarcodeManually(code: String) {
        if (code.isNotBlank()) {
            processBarcode(code)
        }
    }

    private fun processBarcode(barcode: String) {
        val currentBarcodes = _barcodeResults.value.toMutableList()
        val result = BarcodeResult(code = barcode)

        // Verificar se ja existe (evitar duplicatas recentes)
        if (currentBarcodes.none { it.code == result.code &&
            (System.currentTimeMillis() - it.timestamp) < 2000 }) {
            currentBarcodes.add(result)
            _barcodeResults.value = currentBarcodes
            Log.d(TAG, "New barcode: ${result.code}")
        }
    }

    fun clearBarcodes() {
        _barcodeResults.value = emptyList()
    }

    // ==================== Device Info & Battery ====================

    private fun updateDeviceInfo() {
        try {
            val batteryLevel = getBatteryLevel()
            val currentPower = try { uhf.power } catch (e: Exception) { 20 }
            val firmware = "" // Firmware version nao disponivel neste SDK

            _deviceInfo.value = DeviceInfo(
                batteryLevel = batteryLevel,
                currentPower = currentPower,
                firmwareVersion = firmware
            )
            Log.d(TAG, "Device info updated - Battery: $batteryLevel%, Power: $currentPower dBm")
        } catch (e: Exception) {
            Log.e(TAG, "Error updating device info", e)
        }
    }

    private fun getBatteryLevel(): Int {
        return try {
            // Tentar obter nivel de bateria via reflexao ou metodo alternativo
            // Se nao disponivel, retorna -1 (desconhecido)
            val method = uhf.javaClass.methods.find {
                it.name.lowercase().contains("battery") && it.parameterCount == 0
            }
            method?.invoke(uhf) as? Int ?: -1
        } catch (e: Exception) {
            Log.e(TAG, "Error getting battery level", e)
            -1
        }
    }

    private fun startBatteryMonitor() {
        batteryMonitorThread = Thread {
            try {
                while (_connectionState.value is ConnectionState.Connected) {
                    updateDeviceInfo()
                    Thread.sleep(30000) // Atualizar a cada 30 segundos
                }
            } catch (e: InterruptedException) {
                Log.d(TAG, "Battery monitor stopped")
            } catch (e: Exception) {
                Log.e(TAG, "Error in battery monitor", e)
            }
        }
        batteryMonitorThread?.start()
    }

    private fun stopBatteryMonitor() {
        batteryMonitorThread?.interrupt()
        batteryMonitorThread = null
    }

    // ==================== Power Control ====================

    fun setPower(power: Int) {
        try {
            val clampedPower = power.coerceIn(5, 30)
            if (uhf.setPower(clampedPower)) {
                _deviceInfo.value = _deviceInfo.value.copy(currentPower = clampedPower)
                Log.d(TAG, "Power set to: $clampedPower dBm")
            } else {
                Log.e(TAG, "Failed to set power")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error setting power", e)
        }
    }

    fun getPower(): Int {
        return try {
            uhf.power
        } catch (e: Exception) {
            Log.e(TAG, "Error getting power", e)
            20 // Default
        }
    }

    fun getConnectionStatus(): ConnectionStatus {
        return uhf.connectStatus
    }

    fun release() {
        try {
            stopReading()
            stopBarcodeReading()
            stopBatteryMonitor()
            disconnect()
            uhf.free()
            Log.d(TAG, "SDK released")
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing SDK", e)
        }
    }
}
