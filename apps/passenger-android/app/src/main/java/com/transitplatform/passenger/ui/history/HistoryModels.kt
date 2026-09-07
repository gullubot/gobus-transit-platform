package com.transitplatform.passenger.ui.history

import com.transitplatform.passenger.data.model.PassengerStopResponse

data class HistoryItem(
    val origin: PassengerStopResponse,
    val destination: PassengerStopResponse,
    val timestamp: Long
)
