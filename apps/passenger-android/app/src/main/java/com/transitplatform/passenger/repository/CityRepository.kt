package com.transitplatform.passenger.repository

import com.transitplatform.passenger.data.local.PassengerPreferences
import com.transitplatform.passenger.data.model.PassengerOrganizationResponse
import com.transitplatform.passenger.data.remote.PassengerApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.firstOrNull

class CityRepository(
    private val api: PassengerApi,
    private val preferences: PassengerPreferences
) {
    suspend fun getCities(): Result<List<PassengerOrganizationResponse>> {
        return api.getCities()
    }

    suspend fun selectCity(cityId: String, cityName: String) {
        preferences.saveSelectedCity(cityId, cityName)
    }

    fun getSelectedCityIdFlow(): Flow<String?> {
        return preferences.selectedCityId
    }

    fun getSelectedCityNameFlow(): Flow<String?> {
        return preferences.selectedCityName
    }
    
    suspend fun hasSelectedCity(): Boolean {
        return preferences.selectedCityId.firstOrNull() != null
    }

    suspend fun clearSelectedCity() {
        // According to instructions: "Logout must: Clear selected city if that is the established product behavior."
        // We will clear it.
        preferences.saveSelectedCity("", "")
    }
}
