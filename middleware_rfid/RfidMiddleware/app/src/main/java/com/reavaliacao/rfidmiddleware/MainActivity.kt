package com.reavaliacao.rfidmiddleware

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.reavaliacao.rfidmiddleware.ui.MainViewModel
import com.reavaliacao.rfidmiddleware.ui.screens.MainScreen
import com.reavaliacao.rfidmiddleware.ui.screens.ReadingScreen
import com.reavaliacao.rfidmiddleware.ui.screens.SettingsScreen
import com.reavaliacao.rfidmiddleware.ui.theme.RfidMiddlewareTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

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

        checkAndRequestPermissions()

        setContent {
            RfidMiddlewareTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    RfidMiddlewareApp()
                }
            }
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
fun RfidMiddlewareApp(
    viewModel: MainViewModel = hiltViewModel()
) {
    val navController = rememberNavController()
    val uiState by viewModel.uiState.collectAsState()

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
                onBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                settings = uiState.settings,
                onUpdateServerUrl = viewModel::updateServerUrl,
                onUpdateAuthToken = viewModel::updateAuthToken,
                onUpdateReaderPower = viewModel::updateReaderPower,
                onUpdateAutoSend = viewModel::updateAutoSend,
                onBack = { navController.popBackStack() }
            )
        }
    }
}
