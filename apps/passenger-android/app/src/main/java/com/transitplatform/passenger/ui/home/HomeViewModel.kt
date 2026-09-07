package com.transitplatform.passenger.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.repository.CityRepository
import com.transitplatform.passenger.repository.LocationRepository
import com.transitplatform.passenger.repository.ServiceRepository
import com.transitplatform.passenger.repository.StopRepository
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

sealed class StopSearchState {
    object Idle : StopSearchState()
    object Loading : StopSearchState()
    data class Success(val stops: List<PassengerStopResponse>) : StopSearchState()
    data class Error(val message: String) : StopSearchState()
}

data class MajorDepotUi(
    val stop: PassengerStopResponse,
    val name: String,
    val serviceCount: Int
)

class HomeViewModel(
    private val cityRepository: CityRepository,
    private val stopRepository: StopRepository,
    private val locationRepository: LocationRepository,
    private val serviceRepository: ServiceRepository? = null
) : ViewModel() {

    // City state: derives from persistent PassengerPreferences via CityRepository
    val selectedCityName: StateFlow<String?> = cityRepository.getSelectedCityNameFlow()
        .stateIn(viewModelScope, SharingStarted.Lazily, null)

    private val _organizationId = MutableStateFlow<String?>(null)
    val organizationId: StateFlow<String?> = _organizationId.asStateFlow()

    // Origin / Destination state
    private val _originStop = MutableStateFlow<PassengerStopResponse?>(null)
    val originStop = _originStop.asStateFlow()

    private val _destinationStop = MutableStateFlow<PassengerStopResponse?>(null)
    val destinationStop = _destinationStop.asStateFlow()

    // Stop Search state
    private val _searchQuery = MutableStateFlow("")
    val searchQuery = _searchQuery.asStateFlow()

    private val _stopSearchState = MutableStateFlow<StopSearchState>(StopSearchState.Idle)
    val stopSearchState = _stopSearchState.asStateFlow()

    // Authoritative Major Depots
    private val _depots = MutableStateFlow<List<MajorDepotUi>>(emptyList())
    val depots = _depots.asStateFlow()

    private var allStopsCache = emptyList<PassengerStopResponse>()
    private var activeServicesCount: Int = 0

    init {
        viewModelScope.launch {
            cityRepository.getSelectedCityIdFlow().collect { cityId ->
                _organizationId.value = cityId
                if (!cityId.isNullOrEmpty()) {
                    loadServices(cityId)
                    loadStops(cityId)
                }
            }
        }

        // Debounced local search
        viewModelScope.launch {
            @OptIn(FlowPreview::class)
            _searchQuery.debounce(300).collect { query ->
                filterStops(query)
            }
        }
    }

    private fun loadServices(orgId: String) {
        if (serviceRepository == null) return
        viewModelScope.launch {
            serviceRepository.getServices(orgId).fold(
                onSuccess = { services ->
                    activeServicesCount = services.size
                    if (_depots.value.isNotEmpty()) {
                        _depots.value = _depots.value.map { it.copy(serviceCount = activeServicesCount) }
                    }
                },
                onFailure = {
                    // Fail silently for services count; keep 0
                }
            )
        }
    }

    private fun loadStops(organizationId: String) {
        _stopSearchState.value = StopSearchState.Loading
        viewModelScope.launch {
            stopRepository.getStops(organizationId).fold(
                onSuccess = { stops ->
                    allStopsCache = stops
                    _stopSearchState.value = StopSearchState.Success(stops)
                    _depots.value = extractDepots(stops, activeServicesCount)
                },
                onFailure = { error ->
                    _stopSearchState.value = StopSearchState.Error(error.message ?: "Couldn't load stops. Try again.")
                }
            )
        }
    }

    fun retryLoadStops() {
        val orgId = _organizationId.value
        if (!orgId.isNullOrEmpty()) {
            loadServices(orgId)
            loadStops(orgId)
        }
    }

    fun updateSearchQuery(query: String) {
        _searchQuery.value = query
    }

    fun filterStops(query: String) {
        if (allStopsCache.isEmpty()) return
        
        if (query.isBlank()) {
            _stopSearchState.value = StopSearchState.Success(allStopsCache)
            return
        }

        val lowerQuery = query.lowercase().trim()
        val filtered = allStopsCache.filter {
            it.name.lowercase().contains(lowerQuery) || it.stop_code.lowercase().contains(lowerQuery)
        }
        
        if (filtered.isEmpty()) {
            _stopSearchState.value = StopSearchState.Error("No stops found")
        } else {
            _stopSearchState.value = StopSearchState.Success(filtered)
        }
    }

    fun selectDestination(stop: PassengerStopResponse) {
        _destinationStop.value = stop
        _searchQuery.value = ""
    }

    fun selectOrigin(stop: PassengerStopResponse) {
        _originStop.value = stop
        _searchQuery.value = ""
    }

    fun selectDepot(depot: MajorDepotUi) {
        selectDestination(depot.stop)
    }

    fun swapStops() {
        val currentOrigin = _originStop.value
        val currentDest = _destinationStop.value
        
        _originStop.value = currentDest
        _destinationStop.value = currentOrigin
    }
    
    fun clearDestination() {
        _destinationStop.value = null
    }

    fun clearOrigin() {
        _originStop.value = null
    }

    fun resolveNearestStop() {
        viewModelScope.launch {
            val location = locationRepository.getCurrentLocation()
            if (location != null && allStopsCache.isNotEmpty()) {
                val nearest = locationRepository.calculateNearestStop(location, allStopsCache)
                if (nearest != null) {
                    _originStop.value = nearest
                }
            }
        }
    }

    fun getAllStops(): List<PassengerStopResponse> = allStopsCache

    companion object {
        fun extractDepots(
            stops: List<PassengerStopResponse>,
            serviceCount: Int = 0
        ): List<MajorDepotUi> {
            return stops.filter { stop ->
                val lower = stop.name.lowercase()
                lower.contains("depot") || lower.contains("terminus") || lower.contains("bus stand")
            }.map { stop ->
                MajorDepotUi(
                    stop = stop,
                    name = stop.name.trim(),
                    serviceCount = serviceCount
                )
            }
        }
    }
}

class HomeViewModelFactory(
    private val cityRepository: CityRepository,
    private val stopRepository: StopRepository,
    private val locationRepository: LocationRepository,
    private val serviceRepository: ServiceRepository? = null
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(HomeViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return HomeViewModel(cityRepository, stopRepository, locationRepository, serviceRepository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
