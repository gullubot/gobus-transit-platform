package com.transitplatform.passenger.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * Foundation for persistent passenger state.
 * Uses Jetpack DataStore for non-sensitive preferences like the selected city.
 */
val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "passenger_settings")

class PassengerPreferences(private val context: Context) {
    
    companion object {
        val SELECTED_CITY_ID = stringPreferencesKey("selected_city_id")
        val SELECTED_CITY_NAME = stringPreferencesKey("selected_city_name")
    }

    val selectedCityId: Flow<String?> = context.dataStore.data
        .map { preferences ->
            preferences[SELECTED_CITY_ID]
        }

    val selectedCityName: Flow<String?> = context.dataStore.data
        .map { preferences ->
            preferences[SELECTED_CITY_NAME]
        }

    suspend fun saveSelectedCity(cityId: String, cityName: String) {
        context.dataStore.edit { preferences ->
            preferences[SELECTED_CITY_ID] = cityId
            preferences[SELECTED_CITY_NAME] = cityName
        }
    }
    
    // NOTE: Authentication token (JWT) should NOT be stored in DataStore.
    // It will be stored in EncryptedSharedPreferences (androidx.security:security-crypto)
    // in a future implementation step.
}
