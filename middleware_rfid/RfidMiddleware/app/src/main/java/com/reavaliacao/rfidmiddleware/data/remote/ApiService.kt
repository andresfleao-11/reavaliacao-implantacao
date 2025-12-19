package com.reavaliacao.rfidmiddleware.data.remote

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

data class HealthResponse(
    val status: String,
    val message: String? = null
)

interface ApiService {

    @GET("health")
    suspend fun checkHealth(): Response<HealthResponse>

    @POST("api/rfid/tags")
    suspend fun sendTags(
        @Header("Authorization") token: String,
        @Body request: TagBatchRequest
    ): Response<TagBatchResponse>
}
