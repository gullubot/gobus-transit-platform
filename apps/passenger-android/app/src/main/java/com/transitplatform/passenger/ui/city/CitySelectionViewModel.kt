package com.transitplatform.passenger.ui.city

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerOrganizationResponse
import com.transitplatform.passenger.repository.CityRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

sealed class CitySelectionState {
    object Loading : CitySelectionState()
    data class Success(val cities: List<PassengerOrganizationResponse>) : CitySelectionState()
    data class Error(val message: String) : CitySelectionState()
}

class CitySelectionViewModel(private val repository: CityRepository) : ViewModel() {

    private val _state = MutableStateFlow<CitySelectionState>(CitySelectionState.Loading)
    val state: StateFlow<CitySelectionState> = _state.asStateFlow()

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery.asStateFlow()

    private val _selectedCity = MutableStateFlow<PassengerOrganizationResponse?>(null)
    val selectedCity: StateFlow<PassengerOrganizationResponse?> = _selectedCity.asStateFlow()

    /**
     * Filtered cities based on search query and loaded city list.
     * When the query is empty, returns all cities.
     * Otherwise filters by name (case-insensitive contains).
     */
    val filteredCities: StateFlow<List<PassengerOrganizationResponse>> =
        combine(_state, _searchQuery) { state, query ->
            when (state) {
                is CitySelectionState.Success -> filterCities(state.cities, query)
                else -> emptyList()
            }
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = emptyList()
        )

    companion object {
        fun filterCities(
            cities: List<PassengerOrganizationResponse>,
            query: String
        ): List<PassengerOrganizationResponse> {
            if (query.isBlank()) return cities
            return cities.filter { it.name.contains(query, ignoreCase = true) }
        }
    }

    init {
        loadCities()
    }

    fun loadCities() {
        _state.value = CitySelectionState.Loading
        viewModelScope.launch {
            repository.getCities().fold(
                onSuccess = { cities ->
                    if (cities.isEmpty()) {
                        _state.value = CitySelectionState.Error("No active cities available right now.")
                    } else {
                        _state.value = CitySelectionState.Success(cities)
                    }
                },
                onFailure = { error ->
                    _state.value = CitySelectionState.Error(error.message ?: "Failed to load cities.")
                }
            )
        }
    }

    fun updateSearchQuery(query: String) {
        _searchQuery.value = query
    }

    /**
     * Select a city (local state only, does not persist).
     * The user must tap Continue to confirm and persist.
     */
    fun selectCity(city: PassengerOrganizationResponse) {
        _selectedCity.value = city
    }

    /**
     * Confirm the current selection: persist via CityRepository and invoke navigation callback.
     */
    fun confirmSelection(onConfirmed: () -> Unit) {
        val city = _selectedCity.value ?: return
        viewModelScope.launch {
            repository.selectCity(city.id, city.name)
            onConfirmed()
        }
    }
}

class CitySelectionViewModelFactory(private val repository: CityRepository) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(CitySelectionViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return CitySelectionViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
