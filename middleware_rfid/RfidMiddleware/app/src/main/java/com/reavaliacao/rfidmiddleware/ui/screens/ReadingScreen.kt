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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.reavaliacao.rfidmiddleware.rfid.BarcodeResult
import com.reavaliacao.rfidmiddleware.rfid.DeviceInfo
import com.reavaliacao.rfidmiddleware.rfid.ReadMode
import com.reavaliacao.rfidmiddleware.rfid.RfidTag
import com.reavaliacao.rfidmiddleware.ui.ActiveSession
import com.reavaliacao.rfidmiddleware.ui.MainUiState
import com.reavaliacao.rfidmiddleware.ui.SessionCheckStatus
import com.reavaliacao.rfidmiddleware.ui.SessionSendStatus
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
    onSendToSession: () -> Unit,
    onClearSessionSendStatus: () -> Unit,
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
            // Session Status Banner
            SessionStatusBanner(
                activeSession = uiState.activeSession,
                sessionStatus = uiState.sessionStatus,
                currentReadMode = uiState.readMode
            )

            // Mode Toggle
            ReadModeToggle(
                currentMode = uiState.readMode,
                onModeChange = onSetReadMode,
                enabled = !uiState.isReading,
                activeSession = uiState.activeSession
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
                // Check if reading is allowed based on session
                val canRead = uiState.activeSession != null &&
                    ((uiState.activeSession.readingType == "RFID" && uiState.readMode == ReadMode.RFID) ||
                     (uiState.activeSession.readingType == "BARCODE" && uiState.readMode == ReadMode.BARCODE))

                Button(
                    onClick = { if (uiState.isReading) onStopReading() else onStartReading() },
                    modifier = Modifier.weight(1f),
                    enabled = canRead || uiState.isReading, // Allow stopping even if session ended
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

            // No session warning
            if (uiState.activeSession == null && !uiState.isReading) {
                Spacer(modifier = Modifier.height(8.dp))
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = Color(0xFFFFF3E0) // Light orange
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Warning,
                            contentDescription = null,
                            tint = Color(0xFFE65100),
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Inicie uma sessao de leitura na web primeiro",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFE65100)
                        )
                    }
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

            // Action Buttons - Session Send Button (primary action when session active)
            if (uiState.activeSession != null) {
                val hasReadings = when (uiState.activeSession.readingType) {
                    "RFID" -> uiState.readTags.isNotEmpty()
                    "BARCODE" -> uiState.barcodeResults.isNotEmpty()
                    else -> false
                }

                Button(
                    onClick = onSendToSession,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = hasReadings && !uiState.isReading && uiState.sessionSendStatus !is SessionSendStatus.Sending,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    if (uiState.sessionSendStatus is SessionSendStatus.Sending) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(Icons.Default.Send, contentDescription = null)
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Enviar para Sessao Web")
                }

                Spacer(modifier = Modifier.height(8.dp))
            }

            // Session Send Status
            when (val status = uiState.sessionSendStatus) {
                is SessionSendStatus.Success -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = Success.copy(alpha = 0.15f)
                        ),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Success)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center
                        ) {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = Success,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "${status.addedCount} enviados (total: ${status.totalCount})",
                                color = Success,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }
                is SessionSendStatus.Error -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
                        ),
                        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.error)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.Error,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.error,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = status.message,
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }
                else -> {}
            }

            // Local Save/Sync Buttons (secondary actions)
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
                    Text("Salvar Local")
                }

                OutlinedButton(
                    onClick = onSyncTags,
                    modifier = Modifier.weight(1f),
                    enabled = uiState.unsyncedCount > 0 && uiState.syncStatus !is SyncStatus.Syncing
                ) {
                    if (uiState.syncStatus is SyncStatus.Syncing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(Icons.Default.CloudUpload, contentDescription = null)
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Enviar Local")
                }
            }

            // Sync Status - Card proeminente
            when (val status = uiState.syncStatus) {
                is SyncStatus.Success -> {
                    Spacer(modifier = Modifier.height(12.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = Success.copy(alpha = 0.15f)
                        ),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Success)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center
                        ) {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = Success,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "${status.count} itens enviados com sucesso!",
                                color = Success,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
                is SyncStatus.Error -> {
                    Spacer(modifier = Modifier.height(12.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
                        ),
                        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.error)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.Error,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.error,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = status.message,
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }
                is SyncStatus.Syncing -> {
                    Spacer(modifier = Modifier.height(12.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                        )
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "Enviando para o servidor...",
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
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
                        icon = Icons.Default.Wifi,
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
                        icon = Icons.Default.CropFree,
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
fun SessionStatusBanner(
    activeSession: ActiveSession?,
    sessionStatus: SessionCheckStatus,
    currentReadMode: ReadMode
) {
    if (activeSession != null) {
        val isMatchingMode = (activeSession.readingType == "RFID" && currentReadMode == ReadMode.RFID) ||
                            (activeSession.readingType == "BARCODE" && currentReadMode == ReadMode.BARCODE)

        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 12.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isMatchingMode) Success.copy(alpha = 0.15f) else Color(0xFFFFF3E0)
            ),
            border = androidx.compose.foundation.BorderStroke(
                1.dp,
                if (isMatchingMode) Success else Color(0xFFE65100)
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Animated dot
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .background(
                            color = if (isMatchingMode) Success else Color(0xFFE65100),
                            shape = RoundedCornerShape(6.dp)
                        )
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "Sessao ${activeSession.readingType} Ativa",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (isMatchingMode) Success else Color(0xFFE65100)
                    )
                    if (!isMatchingMode) {
                        Text(
                            text = "Mude para modo ${activeSession.readingType} para ler",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFE65100)
                        )
                    }
                    if (activeSession.location != null) {
                        Text(
                            text = "Local: ${activeSession.location}",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray
                        )
                    }
                }
                Icon(
                    if (isMatchingMode) Icons.Default.CheckCircle else Icons.Default.SwapHoriz,
                    contentDescription = null,
                    tint = if (isMatchingMode) Success else Color(0xFFE65100)
                )
            }
        }
    }
}

@Composable
fun ReadModeToggle(
    currentMode: ReadMode,
    onModeChange: (ReadMode) -> Unit,
    enabled: Boolean,
    activeSession: ActiveSession? = null
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
            val rfidHighlight = activeSession?.readingType == "RFID"
            Button(
                onClick = { onModeChange(ReadMode.RFID) },
                modifier = Modifier.weight(1f),
                enabled = enabled,
                colors = ButtonDefaults.buttonColors(
                    containerColor = when {
                        currentMode == ReadMode.RFID && rfidHighlight -> Success
                        currentMode == ReadMode.RFID -> MaterialTheme.colorScheme.primary
                        else -> MaterialTheme.colorScheme.surface
                    },
                    contentColor = if (currentMode == ReadMode.RFID)
                        MaterialTheme.colorScheme.onPrimary
                    else
                        MaterialTheme.colorScheme.onSurface
                )
            ) {
                Icon(Icons.Default.Wifi, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("RFID")
            }

            // Barcode Button
            val barcodeHighlight = activeSession?.readingType == "BARCODE"
            Button(
                onClick = { onModeChange(ReadMode.BARCODE) },
                modifier = Modifier.weight(1f),
                enabled = enabled,
                colors = ButtonDefaults.buttonColors(
                    containerColor = when {
                        currentMode == ReadMode.BARCODE && barcodeHighlight -> Success
                        currentMode == ReadMode.BARCODE -> MaterialTheme.colorScheme.primary
                        else -> MaterialTheme.colorScheme.surface
                    },
                    contentColor = if (currentMode == ReadMode.BARCODE)
                        MaterialTheme.colorScheme.onPrimary
                    else
                        MaterialTheme.colorScheme.onSurface
                )
            ) {
                Icon(Icons.Default.CropFree, contentDescription = null)
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

    // Usar icones mais basicos que existem em todas versoes
    val batteryIcon = when {
        batteryLevel < 0 -> Icons.Default.BatteryAlert
        batteryLevel <= 20 -> Icons.Default.BatteryAlert
        batteryLevel <= 50 -> Icons.Default.Battery3Bar
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
