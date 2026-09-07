package com.transitplatform.passenger.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.transitplatform.passenger.data.model.PassengerLoginResponse

/**
 * Securely stores authentication tokens using Android Jetpack Security.
 */
class PassengerSessionStore(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val sharedPreferences: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "passenger_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveSession(loginResponse: PassengerLoginResponse) {
        sharedPreferences.edit()
            .putString("access_token", loginResponse.access_token)
            .putString("user_id", loginResponse.user_id)
            .putString("name", loginResponse.name)
            .putString("phone", loginResponse.phone)
            .apply()
    }

    fun getAccessToken(): String? {
        return sharedPreferences.getString("access_token", null)
    }

    fun getUserName(): String? {
        return sharedPreferences.getString("name", null)
    }

    fun clearSession() {
        sharedPreferences.edit().clear().apply()
    }

    fun isLoggedIn(): Boolean {
        return getAccessToken() != null
    }
}
