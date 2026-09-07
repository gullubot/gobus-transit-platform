package com.transitplatform.passenger.ui.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.local.HistoryStore
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

class HistoryViewModel(
    private val historyStore: HistoryStore,
    private val organizationId: String
) : ViewModel() {

    val historyList: StateFlow<List<HistoryItem>> = historyStore.getHistoryFlow(organizationId)
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = emptyList()
        )
}

class HistoryViewModelFactory(
    private val historyStore: HistoryStore,
    private val organizationId: String
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(HistoryViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return HistoryViewModel(historyStore, organizationId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
