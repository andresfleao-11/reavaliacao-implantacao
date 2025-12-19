package com.reavaliacao.rfidmiddleware.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [TagEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun tagDao(): TagDao
}
