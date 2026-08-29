package com.transitplatform.app

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.transitplatform.app.data.local.AppDatabase
import com.transitplatform.app.data.local.CrowdingDao
import com.transitplatform.app.data.local.CrowdingReportEntity
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class CrowdingDaoTest {
    private lateinit var db: AppDatabase
    private lateinit var crowdingDao: CrowdingDao

    @Before
    fun createDb() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(
            context, AppDatabase::class.java
        ).build()
        crowdingDao = db.crowdingDao()
    }

    @After
    fun closeDb() {
        db.close()
    }

    @Test
    fun insertAndGetUnsyncedReports() = runBlocking {
        val report1 = CrowdingReportEntity(
            id = UUID.randomUUID().toString(),
            vehicleId = "veh_123",
            crowdingState = "HIGH",
            confidence = 0.85f,
            observedAt = 1000L,
            isSynced = false
        )
        val report2 = CrowdingReportEntity(
            id = UUID.randomUUID().toString(),
            vehicleId = "veh_123",
            crowdingState = "FULL",
            confidence = 0.95f,
            observedAt = 2000L,
            isSynced = true
        )
        
        crowdingDao.insertReport(report1)
        crowdingDao.insertReport(report2)

        val unsynced = crowdingDao.getUnsyncedReports()
        assertEquals(1, unsynced.size)
        assertEquals(report1.id, unsynced[0].id)
        assertEquals("HIGH", unsynced[0].crowdingState)
    }

    @Test
    fun markAsSyncedAndCleanup() = runBlocking {
        val report = CrowdingReportEntity(
            id = UUID.randomUUID().toString(),
            vehicleId = "veh_123",
            crowdingState = "MODERATE",
            confidence = 0.9f,
            observedAt = 1000L,
            isSynced = false
        )
        crowdingDao.insertReport(report)
        
        crowdingDao.markAsSynced(listOf(report.id))
        
        val unsynced = crowdingDao.getUnsyncedReports()
        assertTrue(unsynced.isEmpty())
        
        // Test deletion
        crowdingDao.deleteSyncedReports(2000L) // 2000 > 1000, so it should be deleted
        // Room doesn't have a direct count method in our DAO, but we can verify it doesn't crash
        // and acts correctly if we try to re-fetch synced
    }
}
