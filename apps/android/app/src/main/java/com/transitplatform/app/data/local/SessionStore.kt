package com.transitplatform.app.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.transitplatform.app.data.model.LoginResponse

/**
 * Secure Session Storage for Transit Platform Operator Application.
 *
 * Encrypts sensitive session tokens and operator profile data at rest using
 * AndroidX Jetpack Security (EncryptedSharedPreferences with AES-256 GCM/SIV).
 *
 * CRITICAL SECURITY CONSTRAINTS:
 * - Plaintext credentials and access tokens are never written to disk or logged.
 * - Routing hints (last_trip_id, last_vehicle_id, last_service_code) are NOT
 *   authoritative duty state and are only used as navigation hints until authoritative
 *   trips are fetched.
 */
class SessionStore(
    private val sharedPreferences: SharedPreferences
) {

    constructor(context: Context) : this(
        createEncryptedPreferences(context)
    )

    fun saveSession(loginResponse: LoginResponse) {
        sharedPreferences.edit()
            .putString(KEY_ACCESS_TOKEN, loginResponse.access_token)
            .putString(KEY_TOKEN_TYPE, loginResponse.token_type)
            .putString(KEY_USER_ID, loginResponse.user_id)
            .putString(KEY_NAME, loginResponse.name)
            .putString(KEY_ROLE, loginResponse.role)
            .putString(KEY_EMPLOYEE_CODE, loginResponse.employee_code)
            .putString(KEY_ORG_ID, loginResponse.organization_id)
            .putString(KEY_ORG_NAME, loginResponse.organization_name)
            .apply()
    }

    fun getSession(): LoginResponse? {
        val token = sharedPreferences.getString(KEY_ACCESS_TOKEN, null) ?: return null
        val userId = sharedPreferences.getString(KEY_USER_ID, null) ?: return null
        val name = sharedPreferences.getString(KEY_NAME, "") ?: ""
        val role = sharedPreferences.getString(KEY_ROLE, "") ?: ""
        val employeeCode = sharedPreferences.getString(KEY_EMPLOYEE_CODE, "") ?: ""
        val orgId = sharedPreferences.getString(KEY_ORG_ID, "") ?: ""
        val orgName = sharedPreferences.getString(KEY_ORG_NAME, "") ?: ""
        val tokenType = sharedPreferences.getString(KEY_TOKEN_TYPE, "bearer") ?: "bearer"

        return LoginResponse(
            access_token = token,
            token_type = tokenType,
            user_id = userId,
            name = name,
            role = role,
            employee_code = employeeCode,
            organization_id = orgId,
            organization_name = orgName
        )
    }

    fun getAccessToken(): String? = sharedPreferences.getString(KEY_ACCESS_TOKEN, null)

    fun hasSession(): Boolean = getAccessToken() != null

    fun clearSession() {
        sharedPreferences.edit().clear().apply()
    }

    /**
     * Routing hints ONLY.
     * These values are NOT authoritative duty state and must be re-verified against
     * authoritative backend/local trip data after session restoration.
     */
    fun saveRoutingHints(tripId: String?, vehicleId: String?, serviceCode: String?) {
        sharedPreferences.edit()
            .putString(KEY_HINT_TRIP_ID, tripId)
            .putString(KEY_HINT_VEHICLE_ID, vehicleId)
            .putString(KEY_HINT_SERVICE_CODE, serviceCode)
            .apply()
    }

    fun getHintTripId(): String? = sharedPreferences.getString(KEY_HINT_TRIP_ID, null)
    fun getHintVehicleId(): String? = sharedPreferences.getString(KEY_HINT_VEHICLE_ID, null)
    fun getHintServiceCode(): String? = sharedPreferences.getString(KEY_HINT_SERVICE_CODE, null)

    companion object {
        private const val PREFS_FILE_NAME = "operator_secure_prefs"

        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_TOKEN_TYPE = "token_type"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_NAME = "name"
        private const val KEY_ROLE = "role"
        private const val KEY_EMPLOYEE_CODE = "employee_code"
        private const val KEY_ORG_ID = "organization_id"
        private const val KEY_ORG_NAME = "organization_name"

        private const val KEY_HINT_TRIP_ID = "hint_last_trip_id"
        private const val KEY_HINT_VEHICLE_ID = "hint_last_vehicle_id"
        private const val KEY_HINT_SERVICE_CODE = "hint_last_service_code"

        private fun createEncryptedPreferences(context: Context): SharedPreferences {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            return EncryptedSharedPreferences.create(
                context,
                PREFS_FILE_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        }
    }
}
