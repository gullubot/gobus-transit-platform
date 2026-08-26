package com.transitplatform.app

import com.transitplatform.app.data.local.TrackingPacketEntity
import com.transitplatform.app.data.model.BatchAckResponse
import com.transitplatform.app.ui.ReadinessCheckState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class OperatorFlowUnitTest {

    @Test
    fun testReadinessCheckEvaluation() {
        val notReady = ReadinessCheckState(
            hasFineLocation = false,
            hasCoarseLocation = true,
            isGpsEnabled = false
        )
        assertFalse(notReady.isReadyToTrack)

        val ready = ReadinessCheckState(
            hasFineLocation = true,
            hasCoarseLocation = true,
            hasNotificationPermission = true,
            isGpsEnabled = true,
            isNetworkAvailable = false // Network unavailable should NOT block offline tracking!
        )
        assertTrue(ready.isReadyToTrack)
    }

    @Test
    fun testTrackingPacketEntityCreation() {
        val pktId = UUID.randomUUID().toString()
        val sessId = UUID.randomUUID().toString()
        val packet = TrackingPacketEntity(
            packetId = pktId,
            sessionId = sessId,
            latitude = 30.7333,
            longitude = 76.7794,
            accuracyM = 4.2f,
            speedMps = 12.0f,
            heading = 90.0f,
            observedAt = "2026-08-26T21:00:00.000Z",
            deviceSequence = 1,
            batteryLevel = 90.0f,
            networkType = "4G",
            gpsStatus = "AVAILABLE"
        )
        assertEquals(pktId, packet.packetId)
        assertEquals(1, packet.deviceSequence)
        assertEquals("PENDING", packet.syncStatus)
    }

    @Test
    fun testBatchAckEvictionCalculation() {
        val pkt1 = UUID.randomUUID().toString()
        val pkt2 = UUID.randomUUID().toString()
        val pkt3 = UUID.randomUUID().toString()

        val ack = BatchAckResponse(
            accepted = listOf(pkt1),
            duplicates = listOf(pkt2),
            retryable = listOf(pkt3),
            rejected = emptyList()
        )

        // Accepted + duplicates are safely evicted from local Room queue
        val toEvict = ack.accepted + ack.duplicates
        assertEquals(2, toEvict.size)
        assertTrue(toEvict.contains(pkt1))
        assertTrue(toEvict.contains(pkt2))
        assertFalse(toEvict.contains(pkt3)) // retryable stays in Room queue!
    }
}
