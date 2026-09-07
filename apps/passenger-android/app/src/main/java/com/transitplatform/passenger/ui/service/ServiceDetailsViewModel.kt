package com.transitplatform.passenger.ui.service

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerDepartureResponse
import com.transitplatform.passenger.data.model.PassengerServiceDetailResponse
import com.transitplatform.passenger.data.model.RouteStopDetail
import com.transitplatform.passenger.repository.ServiceRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ServiceDetailsUiState(
    val loading: Boolean = true,
    val error: String? = null,
    val service: PassengerServiceDetailResponse? = null,
    val activeDirection: String = "A_TO_B", // Default
    val displayedStops: List<RouteStopDetail> = emptyList(),
    val selectedStopId: String? = null,
    val departures: List<PassengerDepartureResponse> = emptyList(),
    val departuresLoading: Boolean = false,
    val departuresError: String? = null,
    val offline: Boolean = false
)

class ServiceDetailsViewModel(
    private val serviceRepository: ServiceRepository,
    private val serviceId: String
) : ViewModel() {

    private val _state = MutableStateFlow(ServiceDetailsUiState())
    val state: StateFlow<ServiceDetailsUiState> = _state.asStateFlow()

    init {
        loadServiceDetails()
    }

    fun loadServiceDetails() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            serviceRepository.getServiceDetails(serviceId).fold(
                onSuccess = { details ->
                    _state.value = _state.value.copy(
                        loading = false,
                        service = details,
                        displayedStops = calculateDisplayedStops(details.stops, _state.value.activeDirection),
                        error = null
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = "Unable to load this service."
                    )
                }
            )
        }
    }

    fun setDirection(direction: String) {
        val currentService = _state.value.service ?: return
        if (_state.value.activeDirection != direction) {
            _state.value = _state.value.copy(
                activeDirection = direction,
                displayedStops = calculateDisplayedStops(currentService.stops, direction),
                selectedStopId = null,
                departures = emptyList(),
                departuresError = null
            )
        }
    }

    fun selectStop(stopId: String) {
        _state.value = _state.value.copy(selectedStopId = stopId)
        loadDepartures(stopId, _state.value.activeDirection)
    }

    fun retryDepartures() {
        val stopId = _state.value.selectedStopId
        if (stopId != null) {
            loadDepartures(stopId, _state.value.activeDirection)
        }
    }

    private fun loadDepartures(stopId: String, direction: String) {
        _state.value = _state.value.copy(departuresLoading = true, departuresError = null, departures = emptyList())
        viewModelScope.launch {
            serviceRepository.getStopDepartures(stopId, serviceId, direction).fold(
                onSuccess = { deps ->
                    _state.value = _state.value.copy(
                        departuresLoading = false,
                        departures = deps,
                        departuresError = null
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        departuresLoading = false,
                        departuresError = "Unable to load departures."
                    )
                }
            )
        }
    }

    private fun calculateDisplayedStops(baseStops: List<RouteStopDetail>, direction: String): List<RouteStopDetail> {
        return if (direction == "B_TO_A") {
            baseStops.reversed()
        } else {
            baseStops
        }
    }
}

class ServiceDetailsViewModelFactory(
    private val serviceRepository: ServiceRepository,
    private val serviceId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(ServiceDetailsViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return ServiceDetailsViewModel(serviceRepository, serviceId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
