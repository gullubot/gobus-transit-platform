package com.transitplatform.passenger.data.remote

import com.transitplatform.passenger.BuildConfig
import com.transitplatform.passenger.data.model.PassengerLoginResponse
import com.transitplatform.passenger.data.model.PassengerOrganizationResponse
import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.data.model.PassengerServiceSearchNearestBus
import com.transitplatform.passenger.data.model.PassengerServiceSearchResponse
import com.transitplatform.passenger.data.model.PassengerServiceSummaryResponse
import com.transitplatform.passenger.data.model.PassengerDepartureResponse
import com.transitplatform.passenger.data.model.PassengerServiceDetailResponse
import com.transitplatform.passenger.ui.plan.PassengerPlanTripResponse
import com.transitplatform.passenger.data.model.PassengerLiveBusResponse
import com.transitplatform.passenger.data.model.PassengerFareCalculationResponse
import com.transitplatform.passenger.data.model.PassengerMatchedSlabResponse
import com.transitplatform.passenger.data.model.RouteStopDetail
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class PassengerApi(private val baseUrl: String = BuildConfig.BASE_URL) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun login(phone: String, name: String): Result<PassengerLoginResponse> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("phone", phone)
                put("name", name)
            }
            val request = Request.Builder()
                .url("$baseUrl/api/auth/passenger/login")
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
            val loginResponse = PassengerLoginResponse(
                access_token = obj.getString("access_token"),
                token_type = obj.optString("token_type", "bearer"),
                user_id = obj.getString("user_id"),
                name = obj.getString("name"),
                role = obj.getString("role"),
                phone = obj.getString("phone")
            )
            Result.success(loginResponse)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getCities(): Result<List<PassengerOrganizationResponse>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/passenger/cities")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to load cities (${response.code})")
                } catch (e: Exception) {
                    "Failed to load cities (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val jsonArray = JSONArray(body)
            val cities = mutableListOf<PassengerOrganizationResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                cities.add(
                    PassengerOrganizationResponse(
                        id = obj.getString("id"),
                        name = obj.getString("name")
                    )
                )
            }
            Result.success(cities)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getOrganizations(): Result<List<PassengerOrganizationResponse>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/passenger/organizations")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to load cities (${response.code})")
                } catch (e: Exception) {
                    "Failed to load cities (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val jsonArray = JSONArray(body)
            val orgs = mutableListOf<PassengerOrganizationResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                orgs.add(
                    PassengerOrganizationResponse(
                        id = obj.getString("id"),
                        name = obj.getString("name")
                    )
                )
            }
            Result.success(orgs)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getStops(cityOrOrgId: String): Result<List<PassengerStopResponse>> = withContext(Dispatchers.IO) {
        try {
            val param = if (cityOrOrgId.contains("-") && cityOrOrgId.length == 36) "organization_id" else "city"
            val request = Request.Builder()
                .url("$baseUrl/api/passenger/stops?$param=$cityOrOrgId")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to load stops (${response.code})")
                } catch (e: Exception) {
                    "Failed to load stops (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val jsonArray = JSONArray(body)
            val stops = mutableListOf<PassengerStopResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                val aliasesList = mutableListOf<String>()
                if (obj.has("aliases") && !obj.isNull("aliases")) {
                    val arr = obj.getJSONArray("aliases")
                    for (j in 0 until arr.length()) {
                        aliasesList.add(arr.getString(j))
                    }
                }
                stops.add(
                    PassengerStopResponse(
                        id = obj.getString("id"),
                        organization_id = obj.getString("organization_id"),
                        stop_code = obj.getString("stop_code"),
                        name = obj.getString("name"),
                        latitude = if (obj.isNull("latitude")) null else obj.getDouble("latitude"),
                        longitude = if (obj.isNull("longitude")) null else obj.getDouble("longitude"),
                        aliases = aliasesList
                    )
                )
            }
            Result.success(stops)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun searchServices(
        cityOrOrgId: String,
        originId: String,
        destinationId: String,
        searchDate: String? = null,
        searchTime: String? = null,
        sortBy: String? = "BEST_MATCH",
        filterBy: String? = "ALL"
    ): Result<List<PassengerServiceSearchResponse>> = withContext(Dispatchers.IO) {
        try {
            val param = if (cityOrOrgId.contains("-") && cityOrOrgId.length == 36) "organization_id" else "city"
            var url = "$baseUrl/api/passenger/services/search" +
                    "?$param=$cityOrOrgId" +
                    "&origin_id=$originId" +
                    "&destination_id=$destinationId"
            if (!searchDate.isNullOrBlank()) {
                url += "&search_date=$searchDate"
            }
            if (!searchTime.isNullOrBlank()) {
                url += "&search_time=$searchTime"
            }
            if (!sortBy.isNullOrBlank()) {
                url += "&sort_by=$sortBy"
            }
            if (!filterBy.isNullOrBlank()) {
                url += "&filter_by=$filterBy"
            }

            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to search services (${response.code})")
                } catch (e: Exception) {
                    "Failed to search services (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val jsonArray = JSONArray(body)
            val services = mutableListOf<PassengerServiceSearchResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                
                var nearestBus: PassengerServiceSearchNearestBus? = null
                if (!obj.isNull("nearest_bus")) {
                    val busObj = obj.getJSONObject("nearest_bus")
                    nearestBus = PassengerServiceSearchNearestBus(
                        vehicle_id = busObj.getString("vehicle_id"),
                        eta_seconds = if (busObj.isNull("eta_seconds")) null else busObj.getInt("eta_seconds"),
                        eta_status = if (busObj.isNull("eta_status")) null else busObj.getString("eta_status"),
                        crowd_level = busObj.optString("crowd_level", "LOW")
                    )
                }

                services.add(
                    PassengerServiceSearchResponse(
                        service_id = obj.getString("service_id"),
                        service_name = obj.getString("service_name"),
                        service_code = if (obj.isNull("service_code")) null else obj.getString("service_code"),
                        route_id = if (obj.isNull("route_id")) null else obj.getString("route_id"),
                        direction = obj.getString("direction"),
                        availability_mode = obj.optString("availability_mode", "SCHEDULED"),
                        departure_mode = obj.optString("departure_mode", "SCHEDULED_DEPARTURE"),
                        arrival_mode = obj.optString("arrival_mode", "SCHEDULED_ARRIVAL"),
                        departure_timestamp = if (obj.isNull("departure_timestamp")) null else obj.getString("departure_timestamp"),
                        arrival_timestamp = if (obj.isNull("arrival_timestamp")) null else obj.getString("arrival_timestamp"),
                        expected_arrival_timestamp = if (obj.isNull("expected_arrival_timestamp")) null else obj.getString("expected_arrival_timestamp"),
                        relative_wait_seconds = if (obj.isNull("relative_wait_seconds")) null else obj.getInt("relative_wait_seconds"),
                        relative_message = if (obj.isNull("relative_message")) null else obj.getString("relative_message"),
                        journey_duration_seconds = if (obj.isNull("journey_duration_seconds")) null else obj.getInt("journey_duration_seconds"),
                        fare = if (obj.isNull("fare")) null else obj.getDouble("fare"),
                        is_direct = obj.optBoolean("is_direct", true),
                        is_ac = obj.optBoolean("is_ac", false),
                        service_type = obj.optString("service_type", "REGULAR"),
                        absolute_origin = if (obj.isNull("absolute_origin")) null else obj.getString("absolute_origin"),
                        absolute_destination = if (obj.isNull("absolute_destination")) null else obj.getString("absolute_destination"),
                        searched_origin = if (obj.isNull("searched_origin")) null else obj.getString("searched_origin"),
                        searched_destination = if (obj.isNull("searched_destination")) null else obj.getString("searched_destination"),
                        stops_count = obj.optInt("stops_count", 0),
                        active_buses_count = obj.optInt("active_buses_count", 0),
                        nearest_bus = nearestBus,
                        ranking_score = if (obj.isNull("ranking_score")) null else obj.getDouble("ranking_score")
                    )
                )
            }
            Result.success(services)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getServiceDetails(serviceId: String): Result<PassengerServiceDetailResponse> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/passenger/services/$serviceId")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Failed to load service details (${response.code})"))
            }

            val obj = JSONObject(body)
            
            val stopsJson = obj.getJSONArray("stops")
            val stops = mutableListOf<RouteStopDetail>()
            for (i in 0 until stopsJson.length()) {
                val sObj = stopsJson.getJSONObject(i)
                stops.add(
                    RouteStopDetail(
                        stop_id = sObj.getString("stop_id"),
                        stop_name = sObj.getString("stop_name"),
                        sequence_number = sObj.getInt("sequence_number"),
                        latitude = if (sObj.isNull("latitude")) null else sObj.getDouble("latitude"),
                        longitude = if (sObj.isNull("longitude")) null else sObj.getDouble("longitude"),
                        nominal_travel_time_seconds = if (sObj.has("nominal_travel_time_seconds") && !sObj.isNull("nominal_travel_time_seconds")) sObj.getInt("nominal_travel_time_seconds") else null
                    )
                )
            }

            val details = PassengerServiceDetailResponse(
                id = obj.getString("id"),
                service_name = obj.getString("service_name"),
                route_name = obj.getString("route_name"),
                route_geometry = if (obj.isNull("route_geometry")) null else obj.getJSONObject("route_geometry").toString(),
                stops = stops
            )
            Result.success(details)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getLiveBuses(serviceId: String): Result<List<PassengerLiveBusResponse>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/api/passenger/services/$serviceId/live")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Failed to load live buses (${response.code})"))
            }

            val jsonArray = JSONArray(body)
            val buses = mutableListOf<PassengerLiveBusResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                buses.add(
                    PassengerLiveBusResponse(
                        vehicle_id = obj.getString("vehicle_id"),
                        latitude = if (obj.isNull("latitude")) null else obj.getDouble("latitude"),
                        longitude = if (obj.isNull("longitude")) null else obj.getDouble("longitude"),
                        direction = if (obj.isNull("direction")) null else obj.getString("direction"),
                        current_stop_id = if (obj.isNull("current_stop_id")) null else obj.getString("current_stop_id"),
                        next_stop_id = if (obj.isNull("next_stop_id")) null else obj.getString("next_stop_id"),
                        eta_seconds = if (obj.isNull("eta_seconds")) null else obj.getInt("eta_seconds"),
                        eta_status = if (obj.isNull("eta_status")) null else obj.getString("eta_status"),
                        crowd_level = obj.getString("crowd_level"),
                        state = obj.getString("state"),
                        last_updated_at = if (obj.isNull("last_updated_at")) null else obj.getString("last_updated_at")
                    )
                )
            }
            Result.success(buses)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getServices(organizationId: String): Result<List<PassengerServiceSummaryResponse>> = withContext(Dispatchers.IO) {
        try {
            val param = if (organizationId.contains("-") && organizationId.length == 36) "organization_id" else "city"
            val request = Request.Builder()
                .url("$baseUrl/api/passenger/services?$param=$organizationId")
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Failed to load services (${response.code})"))
            }

            val jsonArray = JSONArray(body)
            val services = mutableListOf<PassengerServiceSummaryResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                services.add(
                    PassengerServiceSummaryResponse(
                        id = obj.getString("id"),
                        organization_id = obj.getString("organization_id"),
                        service_code = obj.getString("service_code"),
                        service_name = obj.getString("service_name"),
                        route_id = obj.getString("route_id")
                    )
                )
            }
            Result.success(services)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getStopDepartures(
        stopId: String,
        serviceId: String,
        direction: String
    ): Result<List<PassengerDepartureResponse>> = withContext(Dispatchers.IO) {
        try {
            val url = "$baseUrl/api/passenger/stops/$stopId/departures?service_id=$serviceId&direction=$direction"
            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Failed to load departures (${response.code})"))
            }

            val jsonArray = JSONArray(body)
            val departures = mutableListOf<PassengerDepartureResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                departures.add(
                    PassengerDepartureResponse(
                        service_id = obj.getString("service_id"),
                        service_name = obj.getString("service_name"),
                        direction = obj.getString("direction"),
                        route_origin = obj.getString("route_origin"),
                        route_destination = obj.getString("route_destination"),
                        scheduled_time = if (obj.isNull("scheduled_time")) null else obj.getString("scheduled_time"),
                        expected_time = if (obj.isNull("expected_time")) null else obj.getString("expected_time"),
                        status = obj.getString("status")
                    )
                )
            }
            Result.success(departures)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun planTrip(
        organizationId: String,
        originId: String,
        destinationId: String,
        date: String,
        time: String
    ): Result<List<PassengerPlanTripResponse>> = withContext(Dispatchers.IO) {
        try {
            val url = "$baseUrl/api/passenger/plan?organization_id=$organizationId&origin_id=$originId&destination_id=$destinationId&date=$date&time=$time"
            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(IOException("Failed to plan trip (${response.code})"))
            }

            val jsonArray = JSONArray(body)
            val trips = mutableListOf<PassengerPlanTripResponse>()
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                trips.add(
                    PassengerPlanTripResponse(
                        service_id = obj.getString("service_id"),
                        service_name = obj.getString("service_name"),
                        direction = obj.getString("direction"),
                        route_origin = obj.getString("route_origin"),
                        route_destination = obj.getString("route_destination"),
                        scheduled_departure = if (obj.isNull("scheduled_departure")) null else obj.getString("scheduled_departure"),
                        scheduled_arrival = if (obj.isNull("scheduled_arrival")) null else obj.getString("scheduled_arrival")
                    )
                )
            }
            Result.success(trips)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun calculateFare(
        organizationId: String,
        serviceId: String,
        originStopId: String,
        destinationStopId: String
    ): Result<PassengerFareCalculationResponse> = withContext(Dispatchers.IO) {
        try {
            val url = "$baseUrl/api/passenger/fares/calculate" +
                    "?organization_id=$organizationId" +
                    "&service_id=$serviceId" +
                    "&origin_stop_id=$originStopId" +
                    "&destination_stop_id=$destinationStopId"

            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                val errorMsg = try {
                    JSONObject(body).optString("detail", "Failed to calculate fare (${response.code})")
                } catch (e: Exception) {
                    "Failed to calculate fare (${response.code})"
                }
                return@withContext Result.failure(IOException(errorMsg))
            }

            val obj = JSONObject(body)
            val slabObj = obj.getJSONObject("matched_slab")
            val matchedSlab = PassengerMatchedSlabResponse(
                id = slabObj.getString("id"),
                min_distance_km = slabObj.getDouble("min_distance_km"),
                max_distance_km = if (slabObj.isNull("max_distance_km")) null else slabObj.getDouble("max_distance_km"),
                fare_amount = slabObj.getDouble("fare_amount")
            )

            val fareResponse = PassengerFareCalculationResponse(
                distance_km = obj.getDouble("distance_km"),
                fare_amount = obj.getDouble("fare_amount"),
                currency = obj.getString("currency"),
                matched_slab = matchedSlab,
                fare_configuration_id = obj.getString("fare_configuration_id"),
                fare_configuration_name = obj.getString("fare_configuration_name")
            )
            Result.success(fareResponse)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
