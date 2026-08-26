package com.transitplatform.app.service

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.transitplatform.app.data.local.AppDatabase
import com.transitplatform.app.data.network.ApiClient
import java.util.concurrent.TimeUnit

/**
 * WorkManager worker for durable, deferred telemetry synchronization.
 *
 * Architecture boundary:
 * - Foreground Service: Continuous GPS location acquisition & immediate Room persistence.
 * - Live Flush: Lightweight opportunistic send while active.
 * - TelemetrySyncWorker (WorkManager): Durable deferred synchronization and retry when network
 *   reconnects or after process/service restarts.
 */
class TelemetrySyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    private val database = AppDatabase.getInstance(appContext)
    private val apiClient = ApiClient()

    override suspend fun doWork(): Result {
        val token = inputData.getString(KEY_TOKEN)
        val sessionId = inputData.getString(KEY_SESSION_ID)
        val baseUrl = inputData.getString(KEY_BASE_URL)

        if (baseUrl != null) {
            apiClient.setBaseUrl(baseUrl)
        }

        if (token.isNullOrEmpty() || sessionId.isNullOrEmpty()) {
            return Result.failure()
        }

        val pendingPackets = database.trackingPacketDao().getPendingPackets(limit = 100)
        if (pendingPackets.isEmpty()) {
            return Result.success()
        }

        val result = apiClient.uploadBatch(token, sessionId, pendingPackets)
        return if (result.isSuccess) {
            val ack = result.getOrNull()
            if (ack != null) {
                val toDelete = (ack.accepted + ack.duplicates).distinct()
                if (toDelete.isNotEmpty()) {
                    database.trackingPacketDao().deletePacketsByIds(toDelete)
                }
            }
            Result.success()
        } else {
            Result.retry()
        }
    }

    companion object {
        const val KEY_TOKEN = "key_token"
        const val KEY_SESSION_ID = "key_session_id"
        const val KEY_BASE_URL = "key_base_url"

        fun scheduleDurableSync(
            context: Context,
            token: String,
            sessionId: String,
            baseUrl: String? = null
        ) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val inputData = androidx.work.Data.Builder()
                .putString(KEY_TOKEN, token)
                .putString(KEY_SESSION_ID, sessionId)
                .apply { if (baseUrl != null) putString(KEY_BASE_URL, baseUrl) }
                .build()

            val syncRequest = OneTimeWorkRequestBuilder<TelemetrySyncWorker>()
                .setConstraints(constraints)
                .setInputData(inputData)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context).enqueue(syncRequest)
        }
    }
}
