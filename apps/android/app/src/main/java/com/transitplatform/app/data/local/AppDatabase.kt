package com.transitplatform.app.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [TrackingPacketEntity::class, CrowdingReportEntity::class], version = 2, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {

    abstract fun trackingPacketDao(): TrackingPacketDao
    abstract fun crowdingDao(): CrowdingDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "transit_operator_local.db"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
