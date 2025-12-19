package com.reavaliacao.rfidmiddleware.data.remote

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

data class HealthResponse(
    val status: String,
    val message: String? = null
)

// Resposta de sessão ativa
data class ActiveSessionResponse(
    val has_active_session: Boolean,
    val session_id: Int? = null,
    val reading_type: String? = null,  // "RFID" ou "BARCODE"
    val project_id: Int? = null,
    val location: String? = null,
    val expires_at: String? = null
)

// Request para enviar leituras para sessão
data class SessionReadingRequest(
    val code: String,
    val rssi: String? = null,
    val device_id: String? = null
)

data class BulkReadingsRequest(
    val readings: List<SessionReadingRequest>
)

data class BulkReadingsResponse(
    val success: Boolean,
    val added_count: Int,
    val total_count: Int
)

interface ApiService {

    @GET("health")
    suspend fun checkHealth(): Response<HealthResponse>

    @POST("api/rfid/tags")
    suspend fun sendTags(
        @Header("Authorization") token: String,
        @Body request: TagBatchRequest
    ): Response<TagBatchResponse>

    // Verificar se há sessão ativa para um usuário
    @GET("api/reading-sessions/app/check")
    suspend fun checkActiveSession(
        @Query("user_id") userId: Int
    ): Response<ActiveSessionResponse>

    // Enviar leituras para uma sessão
    @POST("api/reading-sessions/app/readings/{session_id}")
    suspend fun sendSessionReadings(
        @Path("session_id") sessionId: Int,
        @Body request: BulkReadingsRequest
    ): Response<BulkReadingsResponse>
}
