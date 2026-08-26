package com.transitplatform.app.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "tracking_packets")
data class TrackingPacketEntity(
    @PrimaryKey
    val packetId: String,
    val sessionId: String,
    val latitude: Double,
    val longitude: Double,
    val accuracyM: Float?,
    val speedMps: Float?,
    val heading: Float?,
    val observedAt: String,
    val deviceSequence: Int,
    val batteryLevel: Float?,
    val networkType: String?,
    val gpsStatus: String?,
    val syncStatus: String = "PENDING", // PENDING, SYNCING, RETRYABLE
    val createdAt: Long = System.currentTimeMillis()
)
