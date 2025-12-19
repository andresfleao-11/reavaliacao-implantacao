package com.reavaliacao.rfidmiddleware.data.remote

import android.util.Log
import com.reavaliacao.rfidmiddleware.data.SettingsDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Interceptor que substitui dinamicamente a URL base das requisições
 * usando a URL configurada nas settings do app.
 */
@Singleton
class DynamicBaseUrlInterceptor @Inject constructor(
    private val settingsDataStore: SettingsDataStore
) : Interceptor {

    companion object {
        private const val TAG = "DynamicBaseUrl"
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()

        // Obter a URL configurada (bloqueante, mas necessário no interceptor)
        val serverUrl = runBlocking {
            settingsDataStore.settings.first().serverUrl
        }

        // Se não há URL configurada, usar a original
        if (serverUrl.isBlank()) {
            Log.w(TAG, "No server URL configured, using original: ${originalRequest.url}")
            return chain.proceed(originalRequest)
        }

        // Garantir que a URL tem protocolo
        val normalizedUrl = if (!serverUrl.startsWith("http://") && !serverUrl.startsWith("https://")) {
            "https://$serverUrl"
        } else {
            serverUrl
        }.trimEnd('/')

        val newBaseUrl = normalizedUrl.toHttpUrlOrNull()
        if (newBaseUrl == null) {
            Log.e(TAG, "Invalid server URL: $serverUrl")
            return chain.proceed(originalRequest)
        }

        // Construir nova URL mantendo path e query da requisição original
        val newUrl = originalRequest.url.newBuilder()
            .scheme(newBaseUrl.scheme)
            .host(newBaseUrl.host)
            .port(newBaseUrl.port)
            .build()

        Log.d(TAG, "Redirecting request from ${originalRequest.url} to $newUrl")

        val newRequest = originalRequest.newBuilder()
            .url(newUrl)
            .build()

        return chain.proceed(newRequest)
    }
}
