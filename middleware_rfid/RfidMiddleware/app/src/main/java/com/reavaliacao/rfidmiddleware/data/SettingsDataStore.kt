package com.reavaliacao.rfidmiddleware.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

data class AppSettings(
    val serverUrl: String = "",
    val authToken: String = "",
    val readerPower: Int = 20,
    val autoSend: Boolean = false,
    val lastConnectedDevice: String = ""
)

@Singleton
class SettingsDataStore @Inject constructor(
    private val dataStore: DataStore<Preferences>
) {
    companion object {
        val SERVER_URL = stringPreferencesKey("server_url")
        val AUTH_TOKEN = stringPreferencesKey("auth_token")
        val READER_POWER = intPreferencesKey("reader_power")
        val AUTO_SEND = booleanPreferencesKey("auto_send")
        val LAST_CONNECTED_DEVICE = stringPreferencesKey("last_connected_device")
    }

    val settings: Flow<AppSettings> = dataStore.data.map { preferences ->
        AppSettings(
            serverUrl = preferences[SERVER_URL] ?: "",
            authToken = preferences[AUTH_TOKEN] ?: "",
            readerPower = preferences[READER_POWER] ?: 20,
            autoSend = preferences[AUTO_SEND] ?: false,
            lastConnectedDevice = preferences[LAST_CONNECTED_DEVICE] ?: ""
        )
    }

    suspend fun updateServerUrl(url: String) {
        dataStore.edit { preferences ->
            preferences[SERVER_URL] = url
        }
    }

    suspend fun updateAuthToken(token: String) {
        dataStore.edit { preferences ->
            preferences[AUTH_TOKEN] = token
        }
    }

    suspend fun updateReaderPower(power: Int) {
        dataStore.edit { preferences ->
            preferences[READER_POWER] = power
        }
    }

    suspend fun updateAutoSend(enabled: Boolean) {
        dataStore.edit { preferences ->
            preferences[AUTO_SEND] = enabled
        }
    }

    suspend fun updateLastConnectedDevice(address: String) {
        dataStore.edit { preferences ->
            preferences[LAST_CONNECTED_DEVICE] = address
        }
    }
}
