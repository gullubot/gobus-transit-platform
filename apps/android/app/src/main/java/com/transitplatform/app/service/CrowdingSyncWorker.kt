package com.transitplatform.app.service

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.transitplatform.app.data.local.AppDatabase
import com.transitplatform.app.data.network.ApiClient
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

class CrowdingSyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    private val database = AppDatabase.getInstance(appContext)
    private val apiClient = ApiClient()

    override suspend fun doWork(): Result {
        val token = inputData.getString(KEY_TOKEN)
        val baseUrl = inputData.getString(KEY_BASE_URL)

        if (baseUrl != null) {
            apiClient.setBaseUrl(baseUrl)
        }

        if (token.isNullOrEmpty()) {
            return Result.failure()
        }

        val unsyncedReports = database.crowdingDao().getUnsyncedReports()
        if (unsyncedReports.isEmpty()) {
            return Result.success()
        }

        val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }

        var hasFailure = false
        val syncedIds = mutableListOf<String>()

        for (report in unsyncedReports) {
            val observedAtIso = dateFormat.format(Date(report.observedAt))
            val result = apiClient.uploadCrowdingReport(
                token = token,
                reportId = report.id,
                vehicleId = report.vehicleId,
                crowdingState = report.crowdingState,
                confidence = report.confidence,
                observedAt = observedAtIso
            )

            if (result.isSuccess) {
                syncedIds.add(report.id)
            } else {
                hasFailure = true
            }
        }

        if (syncedIds.isNotEmpty()) {
            database.crowdingDao().markAsSynced(syncedIds)
        }

        return if (hasFailure) {
            Result.retry()
        } else {
            // Clean up old synced reports to save space (e.g. older than 1 day)
            val oneDayAgo = System.currentTimeMillis() - 24 * 60 * 60 * 1000
            database.crowdingDao().deleteSyncedReports(oneDayAgo)
            Result.success()
        }
    }

    companion object {
        const val KEY_TOKEN = "key_token"
        const val KEY_BASE_URL = "key_base_url"
    }
}
