package com.transitplatform.passenger.ui.live

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerLiveBusResponse
import com.transitplatform.passenger.data.model.PassengerServiceDetailResponse
import com.transitplatform.passenger.repository.LiveServiceRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

sealed class ServiceLiveState {
    object Loading : ServiceLiveState()
    data class Success(
        val service: PassengerServiceDetailResponse,
        val buses: List<PassengerLiveBusResponse>,
        val selectedVehicleId: String? = null,
        val isOffline: Boolean = false
    ) : ServiceLiveState()
    data class Error(val message: String) : ServiceLiveState()
}

class ServiceLiveViewModel(
    private val repository: LiveServiceRepository,
    private val serviceId: String
) : ViewModel() {

    private val _state = MutableStateFlow<ServiceLiveState>(ServiceLiveState.Loading)
    val state: StateFlow<ServiceLiveState> = _state.asStateFlow()

    private var pollingJob: Job? = null
    private var serviceDetails: PassengerServiceDetailResponse? = null

    init {
        loadInitialData()
    }

    fun loadInitialData() {
        _state.value = ServiceLiveState.Loading
        viewModelScope.launch {
            repository.getServiceDetails(serviceId).fold(
                onSuccess = { details ->
                    serviceDetails = details
                    startPolling()
                },
                onFailure = {
                    _state.value = ServiceLiveState.Error("Failed to load route details. Please try again.")
                }
            )
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                pollLiveBuses()
                delay(10_000) // 10 seconds polling interval
            }
        }
    }

    private suspend fun pollLiveBuses() {
        repository.getLiveBuses(serviceId).fold(
            onSuccess = { buses ->
                val details = serviceDetails ?: return@fold
                val currentState = _state.value

                // Preserve selected vehicle if still active
                var selectedId: String? = null
                if (currentState is ServiceLiveState.Success) {
                    selectedId = currentState.selectedVehicleId
                    // If selected bus is no longer in the list, clear it
                    if (selectedId != null && buses.none { it.vehicle_id == selectedId }) {
                        selectedId = null
                    }
                }

                _state.value = ServiceLiveState.Success(
                    service = details,
                    buses = buses,
                    selectedVehicleId = selectedId,
                    isOffline = false
                )
            },
            onFailure = {
                val currentState = _state.value
                if (currentState is ServiceLiveState.Success) {
                    // Soft error, mark as offline/failed update but keep UI intact
                    _state.value = currentState.copy(isOffline = true)
                } else if (currentState !is ServiceLiveState.Error) {
                    // If we never loaded successfully, show full error
                    _state.value = ServiceLiveState.Error("Failed to fetch live buses.")
                }
            }
        )
    }

    fun selectBus(vehicleId: String) {
        val currentState = _state.value
        if (currentState is ServiceLiveState.Success) {
            _state.value = currentState.copy(selectedVehicleId = vehicleId)
        }
    }

    fun clearSelection() {
        val currentState = _state.value
        if (currentState is ServiceLiveState.Success) {
            _state.value = currentState.copy(selectedVehicleId = null)
        }
    }

    // Call this if network status changes to offline
    fun pausePolling() {
        pollingJob?.cancel()
        pollingJob = null
        val currentState = _state.value
        if (currentState is ServiceLiveState.Success) {
            _state.value = currentState.copy(isOffline = true)
        }
    }

    // Call this if network status returns
    fun resumePolling() {
        if (pollingJob == null || pollingJob?.isActive != true) {
            startPolling()
        }
    }
}

class ServiceLiveViewModelFactory(
    private val repository: LiveServiceRepository,
    private val serviceId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(ServiceLiveViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return ServiceLiveViewModel(repository, serviceId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
