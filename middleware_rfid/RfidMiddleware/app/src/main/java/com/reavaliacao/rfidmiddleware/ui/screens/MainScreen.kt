package com.reavaliacao.rfidmiddleware.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.reavaliacao.rfidmiddleware.rfid.BleDevice
import com.reavaliacao.rfidmiddleware.rfid.ConnectionState
import com.reavaliacao.rfidmiddleware.rfid.DeviceInfo
import com.reavaliacao.rfidmiddleware.ui.MainUiState
import com.reavaliacao.rfidmiddleware.ui.theme.Success

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    uiState: MainUiState,
    onScanDevices: () -> Unit,
    onStopScan: () -> Unit,
    onConnectDevice: (String) -> Unit,
    onDisconnect: () -> Unit,
    onNavigateToReading: () -> Unit,
    onNavigateToSettings: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("RFID Middleware") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary
                ),
                actions = {
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(
                            Icons.Default.Settings,
                            contentDescription = "Configuracoes",
                            tint = MaterialTheme.colorScheme.onPrimary
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Status Card
            ConnectionStatusCard(
                connectionState = uiState.connectionState,
                deviceInfo = uiState.deviceInfo,
                onDisconnect = onDisconnect
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Action Buttons
            when (uiState.connectionState) {
                is ConnectionState.Connected -> {
                    // Reading Button with icon indicating both modes
                    Button(
                        onClick = onNavigateToReading,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Success
                        )
                    ) {
                        Row(
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Nfc, contentDescription = null)
                            Text(" / ")
                            Icon(Icons.Default.QrCodeScanner, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Iniciar Leitura")
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Quick info about device
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = "Informacoes do Dispositivo",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold
                            )

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Potencia Atual", color = Color.Gray)
                                Text("${uiState.deviceInfo.currentPower} dBm")
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Bateria", color = Color.Gray)
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    BatteryIcon(uiState.deviceInfo.batteryLevel)
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        if (uiState.deviceInfo.batteryLevel >= 0)
                                            "${uiState.deviceInfo.batteryLevel}%"
                                        else
                                            "N/A"
                                    )
                                }
                            }

                            if (uiState.deviceInfo.firmwareVersion.isNotBlank()) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Firmware", color = Color.Gray)
                                    Text(uiState.deviceInfo.firmwareVersion)
                                }
                            }
                        }
                    }

                    if (uiState.unsyncedCount > 0) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.secondaryContainer
                            )
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    Icons.Default.CloudUpload,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.secondary
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "${uiState.unsyncedCount} itens pendentes de sincronizacao",
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                }
                else -> {
                    // Scan Button
                    Button(
                        onClick = {
                            if (uiState.isScanning) onStopScan() else onScanDevices()
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(
                            if (uiState.isScanning) Icons.Default.Stop else Icons.Default.BluetoothSearching,
                            contentDescription = null
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(if (uiState.isScanning) "Parar Scan" else "Escanear Dispositivos")
                    }

                    if (uiState.isScanning) {
                        Spacer(modifier = Modifier.height(8.dp))
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Device List
            if (uiState.connectionState !is ConnectionState.Connected) {
                Text(
                    text = "Dispositivos Encontrados",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(8.dp))

                if (uiState.scannedDevices.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(32.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = if (uiState.isScanning) "Escaneando..." else "Nenhum dispositivo encontrado",
                            color = Color.Gray
                        )
                    }
                } else {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(uiState.scannedDevices) { device ->
                            DeviceCard(
                                device = device,
                                isConnecting = uiState.connectionState is ConnectionState.Connecting,
                                onClick = { onConnectDevice(device.address) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun BatteryIcon(batteryLevel: Int) {
    val batteryColor = when {
        batteryLevel < 0 -> Color.Gray
        batteryLevel <= 20 -> MaterialTheme.colorScheme.error
        batteryLevel <= 50 -> Color(0xFFFF9800) // Orange
        else -> Success
    }

    val batteryIcon = when {
        batteryLevel < 0 -> Icons.Default.BatteryUnknown
        batteryLevel <= 20 -> Icons.Default.Battery1Bar
        batteryLevel <= 40 -> Icons.Default.Battery2Bar
        batteryLevel <= 60 -> Icons.Default.Battery4Bar
        batteryLevel <= 80 -> Icons.Default.Battery5Bar
        else -> Icons.Default.BatteryFull
    }

    Icon(
        batteryIcon,
        contentDescription = "Bateria",
        tint = batteryColor,
        modifier = Modifier.size(20.dp)
    )
}

@Composable
fun ConnectionStatusCard(
    connectionState: ConnectionState,
    deviceInfo: DeviceInfo,
    onDisconnect: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = when (connectionState) {
                is ConnectionState.Connected -> Success.copy(alpha = 0.1f)
                is ConnectionState.Connecting -> MaterialTheme.colorScheme.secondary.copy(alpha = 0.1f)
                else -> MaterialTheme.colorScheme.surfaceVariant
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(
                        when (connectionState) {
                            is ConnectionState.Connected -> Success
                            is ConnectionState.Connecting -> MaterialTheme.colorScheme.secondary
                            else -> Color.Gray
                        }
                    )
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = when (connectionState) {
                        is ConnectionState.Connected -> "Conectado"
                        is ConnectionState.Connecting -> "Conectando..."
                        else -> "Desconectado"
                    },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                if (connectionState is ConnectionState.Connected) {
                    Text(
                        text = connectionState.deviceName,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray
                    )
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = connectionState.deviceAddress,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray
                        )
                        if (deviceInfo.batteryLevel >= 0) {
                            Spacer(modifier = Modifier.width(8.dp))
                            BatteryIcon(deviceInfo.batteryLevel)
                            Text(
                                text = "${deviceInfo.batteryLevel}%",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.Gray
                            )
                        }
                    }
                }
            }

            if (connectionState is ConnectionState.Connected) {
                IconButton(onClick = onDisconnect) {
                    Icon(
                        Icons.Default.LinkOff,
                        contentDescription = "Desconectar",
                        tint = MaterialTheme.colorScheme.error
                    )
                }
            }
        }
    }
}

@Composable
fun DeviceCard(
    device: BleDevice,
    isConnecting: Boolean,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(enabled = !isConnecting) { onClick() }
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Bluetooth,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = device.name ?: "Dispositivo Desconhecido",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = device.address,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }

            Text(
                text = "${device.rssi} dBm",
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )
        }
    }
}
