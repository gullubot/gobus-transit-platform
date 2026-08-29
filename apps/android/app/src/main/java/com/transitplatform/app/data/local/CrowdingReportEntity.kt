package com.transitplatform.app.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.util.UUID

@Entity(tableName = "crowding_reports")
data class CrowdingReportEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val vehicleId: String,
    val crowdingState: String, // e.g., "LOW", "MODERATE", "HIGH", "FULL"
    val confidence: Float,
    val observedAt: Long, // Epoch millis
    val isSynced: Boolean = false,
    val source: String = "OPERATOR" // Since MVP auth role Passenger is skipped, we assume operator app.
)
