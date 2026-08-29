package com.transitplatform.app

import com.transitplatform.app.data.local.CrowdingReportEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class CrowdingUnitTest {

    @Test
    fun testCrowdingReportEntityDefaultValues() {
        val report = CrowdingReportEntity(
            vehicleId = "veh_123",
            crowdingState = "FULL",
            confidence = 0.9f,
            observedAt = 1000L
        )

        assertNotNull(report.id)
        assertTrue(report.id.isNotEmpty())
        assertEquals("veh_123", report.vehicleId)
        assertEquals("FULL", report.crowdingState)
        assertEquals(0.9f, report.confidence)
        assertEquals(1000L, report.observedAt)
        assertEquals(false, report.isSynced)
        assertEquals("OPERATOR", report.source)
    }
    
    @Test
    fun testReportIdPersistenceIsUnique() {
        val report1 = CrowdingReportEntity(
            vehicleId = "veh_123",
            crowdingState = "HIGH",
            confidence = 0.8f,
            observedAt = 1000L
        )
        val report2 = CrowdingReportEntity(
            vehicleId = "veh_123",
            crowdingState = "HIGH",
            confidence = 0.8f,
            observedAt = 1000L
        )
        assertNotEquals(report1.id, report2.id)
    }
}
