package com.transitplatform.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import com.transitplatform.app.ui.ActiveTrackingScreen
import com.transitplatform.app.ui.AssignmentScreen
import com.transitplatform.app.ui.LoginScreen
import com.transitplatform.app.ui.OperatorViewModel
import com.transitplatform.app.ui.ReadinessScreen
import com.transitplatform.app.ui.ScreenState
import com.transitplatform.app.ui.theme.TransitPlatformTheme

class MainActivity : ComponentActivity() {

    private val viewModel: OperatorViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            TransitPlatformTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    OperatorAppRoot(
                        viewModel = viewModel,
                        modifier = Modifier.padding(innerPadding)
                    )
                }
            }
        }
    }
}

@Composable
fun OperatorAppRoot(
    viewModel: OperatorViewModel,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsState()

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) {
        viewModel.checkReadiness()
    }

    fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }

    when (uiState.currentScreen) {
        ScreenState.LOGIN -> {
            LoginScreen(
                uiState = uiState,
                onLogin = { code, pwd -> viewModel.login(code, pwd) },
                onUpdateBaseUrl = { url -> viewModel.updateBaseUrl(url) }
            )
        }
        ScreenState.ASSIGNMENT -> {
            AssignmentScreen(
                uiState = uiState,
                onRefresh = { viewModel.fetchAssignment() },
                onStartTrackingClicked = { viewModel.navigateToReadiness() },
                onLogout = { viewModel.logout() }
            )
        }
        ScreenState.READINESS -> {
            ReadinessScreen(
                uiState = uiState,
                onRequestPermissions = { requestPermissions() },
                onConfirmStart = { viewModel.startTripTracking() },
                onBack = { viewModel.navigateBackToAssignment() }
            )
        }
        ScreenState.TRACKING -> {
            ActiveTrackingScreen(
                uiState = uiState,
                onEndTripClicked = { viewModel.endTripTracking() }
            )
        }
    }
}
