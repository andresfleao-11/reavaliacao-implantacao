package com.reavaliacao.rfidmiddleware.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.reavaliacao.rfidmiddleware.rfid.BarcodeResult
import com.reavaliacao.rfidmiddleware.rfid.DeviceInfo
import com.reavaliacao.rfidmiddleware.rfid.ReadMode
import com.reavaliacao.rfidmiddleware.rfid.RfidTag
import com.reavaliacao.rfidmiddleware.ui.MainUiState
import com.reavaliacao.rfidmiddleware.ui.SyncStatus
import com.reavaliacao.rfidmiddleware.ui.theme.Success
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReadingScreen(
    uiState: MainUiState,
    onStartReading: () -> Unit,
    onStopReading: () -> Unit,
    onClearTags: () -> Unit,
    onSaveTags: () -> Unit,
    onSyncTags: () -> Unit,
    onSetReadMode: (ReadMode) -> Unit,
    onBack: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (uiState.readMode == ReadMode.RFID) "Leitura RFID" else "Leitura Barcode"
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Voltar")
                    }
                },
                actions = {
                    // Battery Indicator
                    BatteryIndicator(deviceInfo = uiState.deviceInfo)
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Mode Toggle
            ReadModeToggle(
                currentMode = uiState.readMode,
                onModeChange = onSetReadMode,
                enabled = !uiState.isReading
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Stats Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    StatItem(
                        label = if (uiState.readMode == ReadMode.RFID) "Tags Lidas" else "Codigos Lidos",
                        value = if (uiState.readMode == ReadMode.RFID)
                            uiState.readTags.size.toString()
                        else
                            uiState.barcodeResults.size.toString()
                    )
                    StatItem(
                        label = "Pendentes",
                        value = uiState.unsyncedCount.toString()
                    )
                    StatItem(
                        label = "Potencia",
                        value = "${uiState.deviceInfo.currentPower} dBm"
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Reading Controls
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Button(
                    onClick = { if (uiState.isReading) onStopReading() else onStartReading() },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (uiState.isReading) MaterialTheme.colorScheme.error else Success
                    )
                ) {
                    Icon(
                        if (uiState.isReading) Icons.Default.Stop else Icons.Default.PlayArrow,
                        contentDescription = null
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(if (uiState.isReading) "Parar" else "Ler")
                }

                OutlinedButton(
                    onClick = onClearTags,
                    enabled = (uiState.readTags.isNotEmpty() || uiState.barcodeResults.isNotEmpty()) && !uiState.isReading
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                }
            }

            if (uiState.isReading) {
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(
                    text = if (uiState.readMode == ReadMode.RFID)
                        "Lendo tags... Aponte o coletor para as etiquetas"
                    else
                        "Lendo codigo de barras... Aponte para o codigo",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = onSaveTags,
                    modifier = Modifier.weight(1f),
                    enabled = (uiState.readTags.isNotEmpty() || uiState.barcodeResults.isNotEmpty()) && !uiState.isReading
                ) {
                    Icon(Icons.Default.Save, contentDescription = null)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Salvar")
                }

                Button(
                    onClick = onSyncTags,
                    modifier = Modifier.weight(1f),
                    enabled = uiState.unsyncedCount > 0 && uiState.syncStatus !is SyncStatus.Syncing
                ) {
                    if (uiState.syncStatus is SyncStatus.Syncing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(Icons.Default.CloudUpload, contentDescription = null)
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Enviar")
                }
            }

            // Sync Status
            when (val status = uiState.syncStatus) {
                is SyncStatus.Success -> {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "${status.count} itens sincronizados com sucesso!",
                        color = Success,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                is SyncStatus.Error -> {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = status.message,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                else -> {}
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Items List
            Text(
                text = if (uiState.readMode == ReadMode.RFID) "Tags Lidas" else "Codigos Lidos",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(8.dp))

            if (uiState.readMode == ReadMode.RFID) {
                // RFID Tags List
                if (uiState.readTags.isEmpty()) {
                    EmptyListPlaceholder(
                        icon = Icons.Default.Nfc,
                        message = "Nenhuma tag lida"
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(uiState.readTags.reversed()) { tag ->
                            TagCard(tag = tag)
                        }
                    }
                }
            } else {
                // Barcode Results List
                if (uiState.barcodeResults.isEmpty()) {
                    EmptyListPlaceholder(
                        icon = Icons.Default.QrCodeScanner,
                        message = "Nenhum codigo lido"
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(uiState.barcodeResults.reversed()) { barcode ->
                            BarcodeCard(barcode = barcode)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ReadModeToggle(
    currentMode: ReadMode,
    onModeChange: (ReadMode) -> Unit,
    enabled: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // RFID Button
            Button(
                onClick = { onModeChange(ReadMode.RFID) },
                modifier = Modifier.weight(1f),
                enabled = enabled,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (currentMode == ReadMode.RFID)
                        MaterialTheme.colorScheme.primary
                    else
                        MaterialTheme.colorScheme.surface,
                    contentColor = if (currentMode == ReadMode.RFID)
                        MaterialTheme.colorScheme.onPrimary
                    else
                        MaterialTheme.colorScheme.onSurface
                )
            ) {
                Icon(Icons.Default.Nfc, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("RFID")
            }

            // Barcode Button
            Button(
                onClick = { onModeChange(ReadMode.BARCODE) },
                modifier = Modifier.weight(1f),
                enabled = enabled,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (currentMode == ReadMode.BARCODE)
                        MaterialTheme.colorScheme.primary
                    else
                        MaterialTheme.colorScheme.surface,
                    contentColor = if (currentMode == ReadMode.BARCODE)
                        MaterialTheme.colorScheme.onPrimary
                    else
                        MaterialTheme.colorScheme.onSurface
                )
            ) {
                Icon(Icons.Default.QrCodeScanner, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Barcode")
            }
        }
    }
}

@Composable
fun BatteryIndicator(deviceInfo: DeviceInfo) {
    val batteryLevel = deviceInfo.batteryLevel
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

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(horizontal = 8.dp)
    ) {
        Icon(
            batteryIcon,
            contentDescription = "Bateria",
            tint = batteryColor,
            modifier = Modifier.size(24.dp)
        )
        if (batteryLevel >= 0) {
            Text(
                text = "$batteryLevel%",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimary
            )
        }
    }
}

@Composable
fun EmptyListPlaceholder(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    message: String
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                icon,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = Color.Gray.copy(alpha = 0.5f)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = message,
                color = Color.Gray
            )
        }
    }
}

@Composable
fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = Color.Gray
        )
    }
}

@Composable
fun TagCard(tag: RfidTag) {
    val dateFormat = remember { SimpleDateFormat("HH:mm:ss", Locale.getDefault()) }

    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Label,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = tag.epc,
                    style = MaterialTheme.typography.bodyMedium,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = "RSSI: ${tag.rssi} dBm",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }

            Text(
                text = dateFormat.format(Date(tag.timestamp)),
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )
        }
    }
}

@Composable
fun BarcodeCard(barcode: BarcodeResult) {
    val dateFormat = remember { SimpleDateFormat("HH:mm:ss", Locale.getDefault()) }

    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.QrCode,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.secondary
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = barcode.code,
                    style = MaterialTheme.typography.bodyMedium,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = barcode.type,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }

            Text(
                text = dateFormat.format(Date(barcode.timestamp)),
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )
        }
    }
}
