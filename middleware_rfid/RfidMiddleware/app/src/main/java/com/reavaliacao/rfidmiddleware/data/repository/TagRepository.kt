package com.reavaliacao.rfidmiddleware.data.repository

import android.util.Log
import com.reavaliacao.rfidmiddleware.data.local.TagDao
import com.reavaliacao.rfidmiddleware.data.local.TagEntity
import com.reavaliacao.rfidmiddleware.data.remote.ApiService
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
}
