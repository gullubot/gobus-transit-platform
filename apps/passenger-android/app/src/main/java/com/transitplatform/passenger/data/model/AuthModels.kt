package com.transitplatform.passenger.data.model

data class PassengerLoginResponse(
    val access_token: String,
    val token_type: String,
    val user_id: String,
    val name: String,
    val role: String,
    val phone: String
)
