package com.reavaliacao.rfidmiddleware

import android.Manifest
import android.content.Intent
import androidx.activity.viewModels
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.reavaliacao.rfidmiddleware.rfid.ReadMode
import com.reavaliacao.rfidmiddleware.ui.MainViewModel
import com.reavaliacao.rfidmiddleware.ui.MainUiState
import com.reavaliacao.rfidmiddleware.ui.screens.MainScreen
import com.reavaliacao.rfidmiddleware.ui.screens.ReadingScreen
import com.reavaliacao.rfidmiddleware.ui.screens.SettingsScreen
import com.reavaliacao.rfidmiddleware.ui.theme.RfidMiddlewareTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    companion object {
        private const val TAG = "MainActivity"
    }

    // Criar ViewModel manualmente (bypass Hilt)
    private val viewModel: MainViewModel by viewModels()

    // Deep link parameters
    private var deepLinkReadingType: String? = null
    private var deepLinkSessionId: Int? = null

    private val requiredPermissions = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        arrayOf(
            Manifest.permission.BLUETOOTH_SCAN,
            Manifest.permission.BLUETOOTH_CONNECT,
            Manifest.permission.ACCESS_FINE_LOCATION
        )
    } else {
        arrayOf(
            Manifest.permission.BLUETOOTH,
            Manifest.permission.BLUETOOTH_ADMIN,
            Manifest.permission.ACCESS_FINE_LOCATION
        )
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.all { it.value }
        if (!allGranted) {
            Toast.makeText(
                this,
                "Permissoes necessarias para usar o Bluetooth",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        android.util.Log.d(TAG, "onCreate started")

        checkAndRequestPermissions()
        android.util.Log.d(TAG, "Permissions checked")

        // Handle deep link
        handleDeepLink(intent)

        try {
            android.util.Log.d(TAG, "Setting content...")
            setContent {
                android.util.Log.d(TAG, "Inside setContent")
                RfidMiddlewareTheme {
                    android.util.Log.d(TAG, "Inside Theme")
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = MaterialTheme.colorScheme.background
                    ) {
                        android.util.Log.d(TAG, "Inside Surface, calling AppContent")
                        AppContent(
                            viewModel = viewModel,
                            deepLinkReadingType = deepLinkReadingType,
                            deepLinkSessionId = deepLinkSessionId,
                            onDeepLinkConsumed = {
                                deepLinkReadingType = null
                                deepLinkSessionId = null
                            }
                        )
                    }
                }
            }
            android.util.Log.d(TAG, "setContent completed")
        } catch (e: Exception) {
            android.util.Log.e(TAG, "Error in setContent", e)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        android.util.Log.d(TAG, "onNewIntent called")
        handleDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent?) {
        val uri = intent?.data
        if (uri != null && uri.scheme == "rfidmiddleware" && uri.host == "reading") {
            android.util.Log.d(TAG, "Deep link received: $uri")

            // Parse parameters: rfidmiddleware://reading?type=RFID&session_id=123
            deepLinkReadingType = uri.getQueryParameter("type")
            deepLinkSessionId = uri.getQueryParameter("session_id")?.toIntOrNull()

            android.util.Log.d(TAG, "Deep link params: type=$deepLinkReadingType, session_id=$deepLinkSessionId")

            // Set the read mode in ViewModel
            when (deepLinkReadingType?.uppercase()) {
                "RFID" -> viewModel.setReadMode(ReadMode.RFID)
                "BARCODE" -> viewModel.setReadMode(ReadMode.BARCODE)
            }

            // Force session check
            viewModel.checkActiveSession()
        }
    }

    private fun checkAndRequestPermissions() {
        val permissionsToRequest = requiredPermissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (permissionsToRequest.isNotEmpty()) {
            permissionLauncher.launch(permissionsToRequest.toTypedArray())
        }
    }
}

sealed class Screen(val route: String) {
    object Main : Screen("main")
    object Reading : Screen("reading")
    object Settings : Screen("settings")
}

@Composable
fun AppContent(
    viewModel: MainViewModel,
    deepLinkReadingType: String? = null,
    deepLinkSessionId: Int? = null,
    onDeepLinkConsumed: () -> Unit = {}
) {
    android.util.Log.d("AppContent", "AppContent started, deepLinkType=$deepLinkReadingType")
    val navController = rememberNavController()
    android.util.Log.d("AppContent", "NavController created")
    val uiState by viewModel.uiState.collectAsState()
    android.util.Log.d("AppContent", "UiState collected")

    // Handle deep link navigation
    LaunchedEffect(deepLinkReadingType) {
        if (deepLinkReadingType != null) {
            android.util.Log.d("AppContent", "Navigating to Reading from deep link")
            navController.navigate(Screen.Reading.route) {
                popUpTo(Screen.Main.route) { inclusive = false }
            }
            onDeepLinkConsumed()
        }
    }

    NavHost(
        navController = navController,
        startDestination = Screen.Main.route
    ) {
        composable(Screen.Main.route) {
            MainScreen(
                uiState = uiState,
                onScanDevices = viewModel::startScanDevices,
                onStopScan = viewModel::stopScanDevices,
                onConnectDevice = viewModel::connectToDevice,
                onDisconnect = viewModel::disconnect,
                onNavigateToReading = { navController.navigate(Screen.Reading.route) },
                onNavigateToSettings = { navController.navigate(Screen.Settings.route) }
            )
        }

        composable(Screen.Reading.route) {
            ReadingScreen(
                uiState = uiState,
                onStartReading = viewModel::startReading,
                onStopReading = viewModel::stopReading,
                onClearTags = viewModel::clearAll,
                onSaveTags = viewModel::saveTagsLocally,
                onSyncTags = viewModel::syncTags,
                onSetReadMode = viewModel::setReadMode,
                onSendToSession = viewModel::sendReadingsToSession,
                onClearSessionSendStatus = viewModel::clearSessionSendStatus,
                onBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                settings = uiState.settings,
                connectionTestStatus = uiState.connectionTestStatus,
                onUpdateServerUrl = viewModel::updateServerUrl,
                onUpdateAuthToken = viewModel::updateAuthToken,
                onUpdateReaderPower = viewModel::updateReaderPower,
                onUpdateAutoSend = viewModel::updateAutoSend,
                onTestConnection = viewModel::testConnection,
                onClearConnectionTestStatus = viewModel::clearConnectionTestStatus,
                onBack = { navController.popBackStack() }
            )
        }
    }
}

// Tela de teste simples - sem Hilt, sem SDK, sem navegacao
@Composable
fun TestScreen() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF1976D2)),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "RFID Middleware",
                fontSize = 28.sp,
                color = Color.White
            )
            Text(
                text = "Teste de UI",
                fontSize = 18.sp,
                color = Color.White.copy(alpha = 0.8f),
                modifier = Modifier.padding(top = 8.dp)
            )
            Text(
                text = "Se voce ve isso, Compose funciona!",
                fontSize = 14.sp,
                color = Color.White.copy(alpha = 0.6f),
                modifier = Modifier.padding(top = 16.dp)
            )
        }
    }
}
