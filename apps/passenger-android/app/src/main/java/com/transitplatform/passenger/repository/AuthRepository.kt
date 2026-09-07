package com.transitplatform.passenger.repository

import com.transitplatform.passenger.data.local.PassengerSessionStore
import com.transitplatform.passenger.data.remote.PassengerApi

class AuthRepository(
    private val api: PassengerApi,
    private val sessionStore: PassengerSessionStore
) {
    suspend fun login(phone: String, name: String): Result<Unit> {
        return api.login(phone, name).map { response ->
            sessionStore.saveSession(response)
        }
    }

    fun isLoggedIn(): Boolean {
        return sessionStore.isLoggedIn()
    }

    fun logout() {
        sessionStore.clearSession()
    }

    fun getUserName(): String? {
        return sessionStore.getUserName()
    }
}
