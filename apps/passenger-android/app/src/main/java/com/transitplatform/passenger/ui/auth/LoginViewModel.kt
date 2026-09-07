package com.transitplatform.passenger.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed class LoginState {
    object Idle : LoginState()
    object Loading : LoginState()
    object Success : LoginState()
    data class Error(val message: String) : LoginState()
}

class LoginViewModel(private val repository: AuthRepository) : ViewModel() {

    private val _state = MutableStateFlow<LoginState>(LoginState.Idle)
    val state: StateFlow<LoginState> = _state.asStateFlow()

    private val _phone = MutableStateFlow("")
    val phone: StateFlow<String> = _phone.asStateFlow()

    private val _name = MutableStateFlow("")
    val name: StateFlow<String> = _name.asStateFlow()

    fun updatePhone(newPhone: String) {
        _phone.value = newPhone
        if (_state.value is LoginState.Error) {
            _state.value = LoginState.Idle
        }
    }

    fun updateName(newName: String) {
        _name.value = newName
        if (_state.value is LoginState.Error) {
            _state.value = LoginState.Idle
        }
    }

    fun login() {
        val currentPhone = phone.value.trim()
        val currentName = name.value.trim()

        if (currentPhone.length < 5) {
            _state.value = LoginState.Error("Please enter a valid phone number.")
            return
        }
        if (currentName.isEmpty()) {
            _state.value = LoginState.Error("Please enter your name.")
            return
        }

        _state.value = LoginState.Loading
        viewModelScope.launch {
            repository.login(currentPhone, currentName).fold(
                onSuccess = {
                    _state.value = LoginState.Success
                },
                onFailure = { error ->
                    _state.value = LoginState.Error(error.message ?: "Login failed. Please try again.")
                }
            )
        }
    }
}

class LoginViewModelFactory(private val repository: AuthRepository) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(LoginViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return LoginViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
