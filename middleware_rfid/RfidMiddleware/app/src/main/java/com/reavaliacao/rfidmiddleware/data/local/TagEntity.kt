package com.reavaliacao.rfidmiddleware.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "tags")
data class TagEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val epc: String,
    val rssi: String,
    val timestamp: Long,
    val synced: Boolean = false,
    val deviceAddress: String = "",
    val batchId: String = ""
)
