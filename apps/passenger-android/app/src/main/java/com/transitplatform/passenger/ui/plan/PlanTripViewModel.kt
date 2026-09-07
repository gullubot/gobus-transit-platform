package com.transitplatform.passenger.ui.plan

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerFareCalculationResponse
import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.repository.FareRepository
import com.transitplatform.passenger.repository.ServiceRepository
import com.transitplatform.passenger.repository.StopRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * Per-service fare UI state.
 * Android performs ZERO fare calculation — this is purely a display state container.
 */
sealed class FareUiState {
    object Idle : FareUiState()
    object Loading : FareUiState()
    data class Success(val fare: PassengerFareCalculationResponse) : FareUiState()
    data class Error(val message: String) : FareUiState()
}

data class PlanTripUiState(
    val origin: PassengerStopResponse? = null,
    val destination: PassengerStopResponse? = null,
    val selectedDate: Date = Date(), // default today
    val selectedTime: String = run {
        val cal = Calendar.getInstance()
        String.format(Locale.US, "%02d:%02d", cal.get(Calendar.HOUR_OF_DAY), cal.get(Calendar.MINUTE))
    },
    val results: List<PassengerPlanTripResponse>? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
    val isOffline: Boolean = false,
    // Per-service fare state keyed by service_id.
    // Each service's fare is fetched independently from the backend.
    val fareStates: Map<String, FareUiState> = emptyMap()
)

class PlanTripViewModel(
    private val serviceRepository: ServiceRepository,
    private val stopRepository: StopRepository,
    private val fareRepository: FareRepository,
    private val organizationId: String
) : ViewModel() {

    private val _state = MutableStateFlow(PlanTripUiState())
    val state: StateFlow<PlanTripUiState> = _state.asStateFlow()

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery.asStateFlow()

    private var allStops = listOf<PassengerStopResponse>()
    private val _filteredStops = MutableStateFlow<List<PassengerStopResponse>>(emptyList())
    val filteredStops: StateFlow<List<PassengerStopResponse>> = _filteredStops.asStateFlow()

    init {
        loadStops()
    }

    private fun loadStops() {
        viewModelScope.launch {
            stopRepository.getStops(organizationId).fold(
                onSuccess = { stops ->
                    allStops = stops
                    filterStops(_searchQuery.value)
                },
                onFailure = {
                    // silently fail or log
                }
            )
        }
    }

    fun updateSearchQuery(query: String) {
        _searchQuery.value = query
        filterStops(query)
    }

    private fun filterStops(query: String) {
        if (query.isBlank()) {
            _filteredStops.value = allStops
        } else {
            _filteredStops.value = allStops.filter {
                it.name.contains(query, ignoreCase = true) || it.stop_code.contains(query, ignoreCase = true)
            }
        }
    }

    fun setOrigin(stop: PassengerStopResponse) {
        _state.value = _state.value.copy(origin = stop, results = null, error = null, fareStates = emptyMap())
    }

    fun setDestination(stop: PassengerStopResponse) {
        _state.value = _state.value.copy(destination = stop, results = null, error = null, fareStates = emptyMap())
    }

    fun setDate(date: Date) {
        _state.value = _state.value.copy(selectedDate = date, results = null, error = null)
    }

    fun setTime(hour: Int, minute: Int) {
        val timeString = String.format(Locale.US, "%02d:%02d", hour, minute)
        _state.value = _state.value.copy(selectedTime = timeString, results = null, error = null)
    }

    fun swapStops() {
        val currentOrigin = _state.value.origin
        val currentDest = _state.value.destination
        _state.value = _state.value.copy(
            origin = currentDest,
            destination = currentOrigin,
            results = null,
            error = null,
            fareStates = emptyMap()
        )
    }

    fun planTrip() {
        val currentState = _state.value
        val origin = currentState.origin ?: return
        val dest = currentState.destination ?: return

        if (origin.id == dest.id) {
            _state.value = currentState.copy(error = "Choose different stops.")
            return
        }

        // Clear stale fare state and results before new search
        _state.value = currentState.copy(isLoading = true, error = null, results = null, fareStates = emptyMap())

        val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val dateString = dateFormat.format(currentState.selectedDate)

        viewModelScope.launch {
            serviceRepository.planTrip(
                organizationId = organizationId,
                originId = origin.id,
                destinationId = dest.id,
                date = dateString,
                time = currentState.selectedTime
            ).fold(
                onSuccess = { trips ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        results = trips,
                        error = null,
                        isOffline = false
                    )
                    // Fetch fares for all distinct services in the results
                    fetchFaresForResults(origin.id, dest.id, trips)
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = "Unable to plan this trip."
                    )
                }
            )
        }
    }

    /**
     * Fetches fares independently for each distinct service_id in the plan trip results.
     * Duplicate service_ids only trigger a single backend request.
     * Each service may have a different fare configuration and thus a different fare.
     */
    private fun fetchFaresForResults(
        originStopId: String,
        destinationStopId: String,
        trips: List<PassengerPlanTripResponse>
    ) {
        val distinctServiceIds = trips.map { it.service_id }.distinct()

        // Set all distinct services to Loading state
        val initialFareStates = distinctServiceIds.associateWith { FareUiState.Loading as FareUiState }
        _state.value = _state.value.copy(fareStates = initialFareStates)

        // Launch independent concurrent coroutines for each service
        for (serviceId in distinctServiceIds) {
            viewModelScope.launch {
                fareRepository.calculateFare(
                    organizationId = organizationId,
                    serviceId = serviceId,
                    originStopId = originStopId,
                    destinationStopId = destinationStopId
                ).fold(
                    onSuccess = { fareResponse ->
                        val currentFareStates = _state.value.fareStates.toMutableMap()
                        currentFareStates[serviceId] = FareUiState.Success(fareResponse)
                        _state.value = _state.value.copy(fareStates = currentFareStates)
                    },
                    onFailure = {
                        val currentFareStates = _state.value.fareStates.toMutableMap()
                        currentFareStates[serviceId] = FareUiState.Error("Fare unavailable")
                        _state.value = _state.value.copy(fareStates = currentFareStates)
                    }
                )
            }
        }
    }
}

class PlanTripViewModelFactory(
    private val serviceRepository: ServiceRepository,
    private val stopRepository: StopRepository,
    private val fareRepository: FareRepository,
    private val organizationId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(PlanTripViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return PlanTripViewModel(serviceRepository, stopRepository, fareRepository, organizationId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
