package com.transitplatform.app.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface TrackingPacketDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(packet: TrackingPacketEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(packets: List<TrackingPacketEntity>)

    @Query("SELECT * FROM tracking_packets WHERE syncStatus = 'PENDING' ORDER BY deviceSequence ASC LIMIT :limit")
    suspend fun getPendingPackets(limit: Int = 50): List<TrackingPacketEntity>

    @Query("DELETE FROM tracking_packets WHERE packetId IN (:packetIds)")
    suspend fun deletePacketsByIds(packetIds: List<String>)

    @Query("SELECT COUNT(*) FROM tracking_packets WHERE syncStatus = 'PENDING'")
    fun countPendingFlow(): Flow<Int>

    @Query("SELECT COUNT(*) FROM tracking_packets WHERE syncStatus = 'PENDING'")
    suspend fun countPending(): Int

    @Query("SELECT MAX(deviceSequence) FROM tracking_packets WHERE sessionId = :sessionId")
    suspend fun getMaxSequenceForSession(sessionId: String): Int?

    @Query("DELETE FROM tracking_packets")
    suspend fun clearAll()
}
