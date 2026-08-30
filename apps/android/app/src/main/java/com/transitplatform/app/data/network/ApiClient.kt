package com.transitplatform.app.data.network

import com.transitplatform.app.data.local.TrackingPacketEntity
import com.transitplatform.app.data.model.AssignmentResponse
import com.transitplatform.app.data.model.BatchAckResponse
import com.transitplatform.app.data.model.HeartbeatResponse
import com.transitplatform.app.data.model.LoginResponse
import com.transitplatform.app.data.model.TripEndResponse
import com.transitplatform.app.data.model.TripStartResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttp
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class ApiClient(private var baseUrl: String = com.transitplatform.app.BuildConfig.BASE_URL) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    fun setBaseUrl(url: String) {
        baseUrl = url.trimEnd('/')
    }

    fun getBaseUrl(): String = baseUrl

    suspend fun login(employeeCode: String, password: String): Result<LoginResponse> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("employee_code", employeeCode)
                put("password", password)
            }
            val request = Request.Builder()
                .url("$baseUrl/api/auth/operator/login")
                .post(json.toString().toRequestBody(jsonMediaType))
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Login failed (${response.code})")
                } catch (e: Exception) {
                    "Login failed (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val obj = JSONObject(body)
            val loginResponse = LoginResponse(
                access_token = obj.getString("access_token"),
                token_type = obj.optString("token_type", "bearer"),
                user_id = obj.getString("user_id"),
                name = obj.getString("name"),
                role = obj.getString("role"),
                employee_code = obj.getString("employee_code"),
                organization_id = obj.getString("organization_id"),
                organization_name = obj.optString("organization_name", "")
            )
            Result.success(loginResponse)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getAssignment(token: String): Result<AssignmentResponse> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/operator/me/assignment")
                .addHeader("Authorization", "Bearer $token")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to fetch assignment (${response.code})")
                } catch (e: Exception) {
                    "Failed to fetch assignment (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val obj = JSONObject(body)
            val assignment = AssignmentResponse(
                assignment_id = obj.getString("assignment_id"),
                trip_id = obj.getString("trip_id"),
                service_id = obj.getString("service_id"),
                service_code = obj.getString("service_code"),
                service_name = obj.getString("service_name"),
                route_id = obj.getString("route_id"),
                route_code = obj.getString("route_code"),
                route_name = obj.getString("route_name"),
                direction = obj.getString("direction"),
                vehicle_id = obj.getString("vehicle_id"),
                vehicle_number = obj.getString("vehicle_number"),
                planned_start_at = obj.getString("planned_start_at"),
                trip_status = obj.getString("trip_status"),
                operator_role = obj.getString("operator_role"),
                assignment_status = obj.getString("assignment_status"),
                assigned_device_id = if (obj.has("assigned_device_id") && !obj.isNull("assigned_device_id")) obj.getString("assigned_device_id") else null,
                assigned_device_status = if (obj.has("assigned_device_status") && !obj.isNull("assigned_device_status")) obj.getString("assigned_device_status") else null,
                active_tracking_session_id = if (obj.has("active_tracking_session_id") && !obj.isNull("active_tracking_session_id")) obj.getString("active_tracking_session_id") else null,
                tracking_session_status = if (obj.has("tracking_session_status") && !obj.isNull("tracking_session_status")) obj.getString("tracking_session_status") else null
            )
            Result.success(assignment)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun startTrip(token: String, tripId: String): Result<TripStartResponse> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/trips/$tripId/start")
                .addHeader("Authorization", "Bearer $token")
                .post("{}".toRequestBody(jsonMediaType))
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to start trip (${response.code})")
                } catch (e: Exception) {
                    "Failed to start trip (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val obj = JSONObject(body)
            val result = TripStartResponse(
                tracking_session_id = obj.getString("tracking_session_id"),
                trip_id = obj.getString("trip_id"),
                device_id = obj.getString("device_id"),
                status = obj.getString("status"),
                started_at = obj.getString("started_at")
            )
            Result.success(result)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun endTrip(token: String, tripId: String): Result<TripEndResponse> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/trips/$tripId/end")
                .addHeader("Authorization", "Bearer $token")
                .post("{}".toRequestBody(jsonMediaType))
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to end trip (${response.code})")
                } catch (e: Exception) {
                    "Failed to end trip (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val obj = JSONObject(body)
            val result = TripEndResponse(
                tracking_session_id = obj.getString("tracking_session_id"),
                trip_id = obj.getString("trip_id"),
                status = obj.getString("status"),
                ended_at = obj.getString("ended_at")
            )
            Result.success(result)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun uploadBatch(
        token: String,
        sessionId: String?,
        packets: List<TrackingPacketEntity>
    ): Result<BatchAckResponse> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject()
            if (sessionId != null) {
                json.put("session_id", sessionId)
            }
            val packetsArray = JSONArray()
            for (p in packets) {
                val pktObj = JSONObject().apply {
                    put("packet_id", p.packetId)
                    put("latitude", p.latitude)
                    put("longitude", p.longitude)
                    if (p.accuracyM != null) put("accuracy_m", p.accuracyM)
                    if (p.speedMps != null) put("speed_mps", p.speedMps)
                    if (p.heading != null) put("heading", p.heading)
                    put("observed_at", p.observedAt)
                    put("device_sequence", p.deviceSequence)
                    if (p.batteryLevel != null) put("battery_level", p.batteryLevel)
                    if (p.networkType != null) put("network_type", p.networkType)
                    if (p.gpsStatus != null) put("gps_status", p.gpsStatus)
                }
                packetsArray.put(pktObj)
            }
            json.put("packets", packetsArray)

            val request = Request.Builder()
                .url("$baseUrl/api/tracking/batch")
                .addHeader("Authorization", "Bearer $token")
                .post(json.toString().toRequestBody(jsonMediaType))
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Batch upload failed (${response.code})")
                } catch (e: Exception) {
                    "Batch upload failed (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val obj = JSONObject(body)
            val acceptedList = mutableListOf<String>()
            val acceptedArr = obj.optJSONArray("accepted")
            if (acceptedArr != null) {
                for (i in 0 until acceptedArr.length()) {
                    acceptedList.add(acceptedArr.getString(i))
                }
            }

            val duplicatesList = mutableListOf<String>()
            val duplicatesArr = obj.optJSONArray("duplicates")
            if (duplicatesArr != null) {
                for (i in 0 until duplicatesArr.length()) {
                    duplicatesList.add(duplicatesArr.getString(i))
                }
            }

            val retryableList = mutableListOf<String>()
            val retryableArr = obj.optJSONArray("retryable")
            if (retryableArr != null) {
                for (i in 0 until retryableArr.length()) {
                    retryableList.add(retryableArr.getString(i))
                }
            }

            val ack = BatchAckResponse(
                accepted = acceptedList,
                duplicates = duplicatesList,
                retryable = retryableList,
                rejected = emptyList()
            )
            return@withContext Result.success(ack)
        } catch (e: Exception) {
            return@withContext Result.failure(e)
        }
    }
    
    suspend fun uploadCrowdingReport(
        token: String,
        reportId: String,
        vehicleId: String,
        crowdingState: String,
        confidence: Float,
        observedAt: String
    ): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("report_id", reportId)
                put("vehicle_id", vehicleId)
                put("crowding_state", crowdingState)
                put("confidence", confidence)
                put("observed_at", observedAt)
            }
            val request = Request.Builder()
                .url("$baseUrl/api/crowding/reports")
                .post(json.toString().toRequestBody(jsonMediaType))
                .header("Authorization", "Bearer $token")
                .build()

            val response = client.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Upload failed (${response.code})"))
            }
            return@withContext Result.success(Unit)
        } catch (e: Exception) {
            return@withContext Result.failure(e)
        }
    }


    suspend fun sendHeartbeat(
        token: String,
        sessionId: String?,
        batteryLevel: Float?,
        networkType: String?,
        gpsStatus: String?
    ): Result<HeartbeatResponse> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                if (sessionId != null) put("session_id", sessionId)
                if (batteryLevel != null) put("battery_level", batteryLevel)
                if (networkType != null) put("network_type", networkType)
                if (gpsStatus != null) put("gps_status", gpsStatus)
                put("app_version", "0.1.0")
            }
            val request = Request.Builder()
                .url("$baseUrl/api/tracking/heartbeat")
                .addHeader("Authorization", "Bearer $token")
                .post(json.toString().toRequestBody(jsonMediaType))
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Heartbeat failed (${response.code})"))
            }

            val obj = JSONObject(body)
            val result = HeartbeatResponse(
                status = obj.getString("status"),
                received_at = obj.getString("received_at"),
                device_status = obj.getString("device_status"),
                session_status = if (obj.has("session_status") && !obj.isNull("session_status")) obj.getString("session_status") else null
            )
            Result.success(result)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
