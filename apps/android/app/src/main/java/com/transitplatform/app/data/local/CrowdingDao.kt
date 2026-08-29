package com.transitplatform.app.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface CrowdingDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertReport(report: CrowdingReportEntity)

    @Query("SELECT * FROM crowding_reports WHERE isSynced = 0 ORDER BY observedAt ASC")
    suspend fun getUnsyncedReports(): List<CrowdingReportEntity>

    @Query("UPDATE crowding_reports SET isSynced = 1 WHERE id IN (:ids)")
    suspend fun markAsSynced(ids: List<String>)
    
    @Query("DELETE FROM crowding_reports WHERE isSynced = 1 AND observedAt < :beforeMillis")
    suspend fun deleteSyncedReports(beforeMillis: Long)
}
