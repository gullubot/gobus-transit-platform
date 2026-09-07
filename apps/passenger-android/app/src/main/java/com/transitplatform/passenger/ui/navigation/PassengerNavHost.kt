package com.transitplatform.passenger.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.navigation
import androidx.navigation.compose.rememberNavController
import com.transitplatform.passenger.data.local.PassengerPreferences
import com.transitplatform.passenger.data.local.PassengerSessionStore
import com.transitplatform.passenger.data.remote.PassengerApi
import kotlinx.coroutines.flow.firstOrNull
import com.transitplatform.passenger.repository.AuthRepository
import com.transitplatform.passenger.repository.CityRepository
import com.transitplatform.passenger.ui.auth.LoginScreen
import com.transitplatform.passenger.ui.auth.LoginViewModel
import com.transitplatform.passenger.ui.auth.LoginViewModelFactory
import com.transitplatform.passenger.ui.city.CitySelectionScreen
import com.transitplatform.passenger.ui.city.CitySelectionViewModel
import com.transitplatform.passenger.ui.city.CitySelectionViewModelFactory
import com.transitplatform.passenger.ui.home.HomePlaceholderScreen
import com.transitplatform.passenger.data.model.PassengerStopResponse

@Composable
fun PassengerNavHost(
    navController: NavHostController = rememberNavController()
) {
    val context = LocalContext.current
    
    // Dependencies
    val api = remember { PassengerApi() }
    val sessionStore = remember { PassengerSessionStore(context) }
    val preferences = remember { PassengerPreferences(context) }
    val locationRepository = remember { com.transitplatform.passenger.repository.LocationRepository(context) }
    
    val authRepository = remember { AuthRepository(api, sessionStore) }
    val cityRepository = remember { CityRepository(api, preferences) }
    val stopRepository = remember { com.transitplatform.passenger.repository.StopRepository(api) }
    val serviceRepository = remember { com.transitplatform.passenger.repository.ServiceRepository(api) }
    val fareRepository = remember { com.transitplatform.passenger.repository.FareRepository(api) }
    val liveServiceRepository = remember { com.transitplatform.passenger.repository.LiveServiceRepository(api) }

    // Start Destination Logic
    var startDestination by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        if (!authRepository.isLoggedIn()) {
            startDestination = "login"
        } else {
            val cityId = cityRepository.getSelectedCityIdFlow().firstOrNull()
            if (cityId.isNullOrEmpty()) {
                startDestination = "city_selection"
            } else {
                startDestination = "main"
            }
        }
    }

    if (startDestination == null) {
        // Still evaluating start destination
        return
    }

    NavHost(
        navController = navController,
        startDestination = startDestination!!
    ) {
        composable("login") {
            val loginViewModel: LoginViewModel = viewModel(
                factory = LoginViewModelFactory(authRepository)
            )
            LoginScreen(
                viewModel = loginViewModel,
                onLoginSuccess = {
                    navController.navigate("city_selection") {
                        popUpTo("login") { inclusive = true }
                    }
                }
            )
        }
        
        composable("city_selection") {
            val cityViewModel: CitySelectionViewModel = viewModel(
                factory = CitySelectionViewModelFactory(cityRepository)
            )
            CitySelectionScreen(
                viewModel = cityViewModel,
                onCitySelected = {
                    navController.navigate("main") {
                        popUpTo("city_selection") { inclusive = true }
                    }
                }
            )
        }
        
        composable("main") {
            val orgId = preferences.selectedCityId.collectAsStateWithLifecycle(initialValue = "").value ?: ""
            if (orgId.isEmpty()) return@composable
            
            // Provide HistoryStore
            val historyStore = remember { com.transitplatform.passenger.data.local.HistoryStore(context) }
            
            com.transitplatform.passenger.ui.main.MainScreen(
                organizationId = orgId,
                cityRepository = cityRepository,
                stopRepository = stopRepository,
                locationRepository = locationRepository,
                serviceRepository = serviceRepository,
                fareRepository = fareRepository,
                historyStore = historyStore,
                rootNavController = navController,
                onLogout = {
                    authRepository.logout()
                    navController.navigate("login") {
                        popUpTo("main") { inclusive = true }
                    }
                },
                onChangeCity = {
                    navController.navigate("city_selection")
                }
            )
        }

        composable(
            route = "nearby_buses/{originId}/{destinationId}?originName={originName}&destName={destName}&initialDateMillis={initialDateMillis}&initialFilter={initialFilter}",
            arguments = listOf(
                androidx.navigation.navArgument("originId") { type = androidx.navigation.NavType.StringType },
                androidx.navigation.navArgument("destinationId") { type = androidx.navigation.NavType.StringType },
                androidx.navigation.navArgument("originName") {
                    type = androidx.navigation.NavType.StringType
                    defaultValue = "Esplanade"
                },
                androidx.navigation.navArgument("destName") {
                    type = androidx.navigation.NavType.StringType
                    defaultValue = "Howrah Station"
                },
                androidx.navigation.navArgument("initialDateMillis") {
                    type = androidx.navigation.NavType.StringType
                    defaultValue = ""
                },
                androidx.navigation.navArgument("initialFilter") {
                    type = androidx.navigation.NavType.StringType
                    defaultValue = ""
                }
            ),
            deepLinks = listOf(
                androidx.navigation.navDeepLink { uriPattern = "gobus://nearby_buses/{originId}/{destinationId}?originName={originName}&destName={destName}&initialDateMillis={initialDateMillis}&initialFilter={initialFilter}" },
                androidx.navigation.navDeepLink { uriPattern = "gobus://nearby_buses/{originId}/{destinationId}?originName={originName}&destName={destName}" }
            )
        ) { backStackEntry ->
            val originId = backStackEntry.arguments?.getString("originId") ?: return@composable
            val destinationId = backStackEntry.arguments?.getString("destinationId") ?: return@composable
            val originName = backStackEntry.arguments?.getString("originName") ?: "Esplanade"
            val destName = backStackEntry.arguments?.getString("destName") ?: "Howrah Station"
            val dateMillisStr = backStackEntry.arguments?.getString("initialDateMillis")
            val initialDateMillis = if (!dateMillisStr.isNullOrBlank()) dateMillisStr.toLongOrNull() else null
            val initialFilter = backStackEntry.arguments?.getString("initialFilter")?.ifBlank { null }

            var orgId = preferences.selectedCityId.collectAsStateWithLifecycle(initialValue = "").value ?: ""
            if (orgId.isEmpty()) {
                orgId = "8ff4c19f-fbdb-5815-bd6d-746203b3865c"
            }

            val nearbyBusViewModel: com.transitplatform.passenger.ui.search.NearbyBusViewModel = viewModel(
                factory = com.transitplatform.passenger.ui.search.NearbyBusViewModelFactory(
                    serviceRepository = serviceRepository,
                    fareRepository = fareRepository,
                    organizationId = orgId,
                    originId = originId,
                    destinationId = destinationId,
                    originName = originName,
                    destinationName = destName,
                    initialDateMillis = initialDateMillis,
                    initialFilterStr = initialFilter
                )
            )

            com.transitplatform.passenger.ui.search.NearbyBusResultsScreen(
                viewModel = nearbyBusViewModel,
                onBack = { navController.popBackStack() },
                onNavigateTab = { _ ->
                    navController.popBackStack()
                },
                onServiceTap = { serviceId ->
                    navController.navigate("service_live/$serviceId")
                }
            )
        }
        composable("service_search") {
            val orgId = preferences.selectedCityId.collectAsStateWithLifecycle(initialValue = "").value ?: ""
            if (orgId.isEmpty()) return@composable

            val searchViewModel: com.transitplatform.passenger.ui.service.ServiceSearchViewModel = viewModel(
                factory = com.transitplatform.passenger.ui.service.ServiceSearchViewModelFactory(
                    serviceRepository = serviceRepository,
                    organizationId = orgId
                )
            )
            com.transitplatform.passenger.ui.service.ServiceSearchScreen(
                viewModel = searchViewModel,
                onBack = { navController.popBackStack() },
                onServiceSelected = { serviceId ->
                    navController.navigate("service_details/$serviceId")
                }
            )
        }
        composable("service_details/{serviceId}") { backStackEntry ->
            val serviceId = backStackEntry.arguments?.getString("serviceId") ?: return@composable
            
            val detailsViewModel: com.transitplatform.passenger.ui.service.ServiceDetailsViewModel = viewModel(
                factory = com.transitplatform.passenger.ui.service.ServiceDetailsViewModelFactory(
                    serviceRepository = serviceRepository,
                    serviceId = serviceId
                )
            )

            com.transitplatform.passenger.ui.service.ServiceDetailsScreen(
                viewModel = detailsViewModel,
                onBack = { navController.popBackStack() },
                onViewLiveBuses = { id ->
                    navController.navigate("service_live/$id")
                }
            )
        }
        composable(
            route = "service_live/{serviceId}",
            deepLinks = listOf(
                androidx.navigation.navDeepLink { uriPattern = "gobus://service_live/{serviceId}" }
            )
        ) { backStackEntry ->
            val serviceId = backStackEntry.arguments?.getString("serviceId") ?: return@composable
            
            val liveViewModel: com.transitplatform.passenger.ui.live.ServiceLiveViewModel = viewModel(
                factory = com.transitplatform.passenger.ui.live.ServiceLiveViewModelFactory(
                    repository = liveServiceRepository,
                    serviceId = serviceId
                )
            )

            com.transitplatform.passenger.ui.live.ServiceLiveScreen(
                viewModel = liveViewModel,
                onBack = { navController.popBackStack() }
            )
        }
    }
}

@Composable
fun PlaceholderScreen(title: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(text = title)
    }
}
