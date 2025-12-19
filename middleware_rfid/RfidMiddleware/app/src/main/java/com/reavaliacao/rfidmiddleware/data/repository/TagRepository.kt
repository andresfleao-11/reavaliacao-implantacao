package com.reavaliacao.rfidmiddleware.data.repository

import android.util.Log
import com.reavaliacao.rfidmiddleware.data.local.TagDao
import com.reavaliacao.rfidmiddleware.data.local.TagEntity
import com.reavaliacao.rfidmiddleware.data.remote.ActiveSessionResponse
import com.reavaliacao.rfidmiddleware.data.remote.ApiService
import com.reavaliacao.rfidmiddleware.data.remote.BulkReadingsRequest
import com.reavaliacao.rfidmiddleware.data.remote.BulkReadingsResponse
import com.reavaliacao.rfidmiddleware.data.remote.SessionReadingRequest
import com.reavaliacao.rfidmiddleware.data.remote.TagBatchRequest
import com.reavaliacao.rfidmiddleware.data.remote.TagDto
import com.reavaliacao.rfidmiddleware.rfid.RfidTag
import kotlinx.coroutines.flow.Flow
import java.text.SimpleDateFormat
import java.util.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TagRepository @Inject constructor(
    private val tagDao: TagDao,
    private val apiService: ApiService
) {
    companion object {
        private const val TAG = "TagRepository"
    }

    fun getAllTags(): Flow<List<TagEntity>> = tagDao.getAllTags()

    fun getUnsyncedCount(): Flow<Int> = tagDao.getUnsyncedCount()

    suspend fun saveTags(tags: List<RfidTag>, deviceAddress: String, batchId: String) {
        val entities = tags.map { tag ->
            TagEntity(
                epc = tag.epc,
                rssi = tag.rssi,
                timestamp = tag.timestamp,
                deviceAddress = deviceAddress,
                batchId = batchId,
                synced = false
            )
        }
        tagDao.insertAll(entities)
        Log.d(TAG, "Saved ${entities.size} tags locally")
    }

    suspend fun syncTags(token: String, deviceId: String): Result<Int> {
        return try {
            val unsyncedTags = tagDao.getUnsyncedTags()
            if (unsyncedTags.isEmpty()) {
                return Result.success(0)
            }

            val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            dateFormat.timeZone = TimeZone.getTimeZone("UTC")

            val tagDtos = unsyncedTags.map { entity ->
                TagDto(
                    epc = entity.epc,
                    rssi = entity.rssi,
                    timestamp = dateFormat.format(Date(entity.timestamp))
                )
            }

            val batchId = unsyncedTags.firstOrNull()?.batchId ?: UUID.randomUUID().toString()

            val request = TagBatchRequest(
                deviceId = deviceId,
                tags = tagDtos,
                batchId = batchId
            )

            val response = apiService.sendTags("Bearer $token", request)

            if (response.isSuccessful && response.body()?.success == true) {
                val ids = unsyncedTags.map { it.id }
                tagDao.markAsSynced(ids)
                Log.d(TAG, "Synced ${ids.size} tags")
                Result.success(ids.size)
            } else {
                val error = response.errorBody()?.string() ?: "Unknown error"
                Log.e(TAG, "Sync failed: $error")
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Sync error", e)
            Result.failure(e)
        }
    }

    suspend fun clearAllTags() {
        tagDao.deleteAll()
    }

    suspend fun clearSyncedTags() {
        tagDao.deleteSynced()
    }

    suspend fun testConnection(): Result<String> {
        return try {
            Log.d(TAG, "Testing connection to server...")
            val response = apiService.checkHealth()

            if (response.isSuccessful) {
                val health = response.body()
                Log.d(TAG, "Connection successful: ${health?.status}")
                Result.success(health?.status ?: "OK")
            } else {
                val error = "Erro HTTP ${response.code()}: ${response.message()}"
                Log.e(TAG, "Connection test failed: $error")
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Connection test error", e)
            Result.failure(e)
        }
    }

    // ==================== Session Management ====================

    suspend fun checkActiveSession(userId: Int): Result<ActiveSessionResponse> {
        return try {
            Log.d(TAG, "Checking active session for user $userId...")
            val response = apiService.checkActiveSession(userId)

            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Log.d(TAG, "Session check response: has_active=${body.has_active_session}, type=${body.reading_type}")
                    Result.success(body)
                } else {
                    Log.d(TAG, "Session check: empty body")
                    Result.success(ActiveSessionResponse(has_active_session = false))
                }
            } else {
                val error = "Erro HTTP ${response.code()}: ${response.message()}"
                Log.e(TAG, "Session check failed: $error")
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Session check error", e)
            Result.failure(e)
        }
    }

    suspend fun sendSessionReadings(
        sessionId: Int,
        readings: List<SessionReadingRequest>
    ): Result<BulkReadingsResponse> {
        return try {
            Log.d(TAG, "Sending ${readings.size} readings to session $sessionId...")
            val request = BulkReadingsRequest(readings = readings)
            val response = apiService.sendSessionReadings(sessionId, request)

            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Log.d(TAG, "Session readings sent: added=${body.added_count}, total=${body.total_count}")
                    Result.success(body)
                } else {
                    Log.e(TAG, "Session readings: empty body")
                    Result.failure(Exception("Empty response body"))
                }
            } else {
                val error = response.errorBody()?.string() ?: "Erro HTTP ${response.code()}"
                Log.e(TAG, "Session readings failed: $error")
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Session readings error", e)
            Result.failure(e)
        }
    }
}
