package com.transitplatform.passenger.ui.service

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerServiceSummaryResponse
import com.transitplatform.passenger.repository.ServiceRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed class ServiceSearchState {
    object Loading : ServiceSearchState()
    data class Success(val services: List<PassengerServiceSummaryResponse>) : ServiceSearchState()
    data class Error(val message: String) : ServiceSearchState()
}

class ServiceSearchViewModel(
    private val serviceRepository: ServiceRepository,
    private val organizationId: String
) : ViewModel() {

    private val _state = MutableStateFlow<ServiceSearchState>(ServiceSearchState.Loading)
    val state: StateFlow<ServiceSearchState> = _state.asStateFlow()

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery.asStateFlow()

    private var allServices = listOf<PassengerServiceSummaryResponse>()

    init {
        loadServices()
    }

    fun loadServices() {
        _state.value = ServiceSearchState.Loading
        viewModelScope.launch {
            serviceRepository.getServices(organizationId).fold(
                onSuccess = { services ->
                    allServices = services
                    filterServices(_searchQuery.value)
                },
                onFailure = {
                    _state.value = ServiceSearchState.Error("Unable to load services.")
                }
            )
        }
    }

    fun updateSearchQuery(query: String) {
        _searchQuery.value = query
        filterServices(query)
    }

    private fun filterServices(query: String) {
        if (allServices.isEmpty()) return
        
        val filtered = if (query.isBlank()) {
            allServices
        } else {
            allServices.filter {
                it.service_name.contains(query, ignoreCase = true) || 
                it.service_code.contains(query, ignoreCase = true) ||
                it.route_id.contains(query, ignoreCase = true)
            }
        }
        _state.value = ServiceSearchState.Success(filtered)
    }
}

class ServiceSearchViewModelFactory(
    private val serviceRepository: ServiceRepository,
    private val organizationId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(ServiceSearchViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return ServiceSearchViewModel(serviceRepository, organizationId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
