package com.reavaliacao.rfidmiddleware.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface TagDao {
    @Query("SELECT * FROM tags ORDER BY timestamp DESC")
    fun getAllTags(): Flow<List<TagEntity>>

    @Query("SELECT * FROM tags WHERE synced = 0 ORDER BY timestamp ASC")
    suspend fun getUnsyncedTags(): List<TagEntity>

    @Query("SELECT COUNT(*) FROM tags WHERE synced = 0")
    fun getUnsyncedCount(): Flow<Int>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(tag: TagEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(tags: List<TagEntity>)

    @Update
    suspend fun update(tag: TagEntity)

    @Query("UPDATE tags SET synced = 1 WHERE id IN (:ids)")
    suspend fun markAsSynced(ids: List<Long>)

    @Query("DELETE FROM tags")
    suspend fun deleteAll()

    @Query("DELETE FROM tags WHERE synced = 1")
    suspend fun deleteSynced()
}
