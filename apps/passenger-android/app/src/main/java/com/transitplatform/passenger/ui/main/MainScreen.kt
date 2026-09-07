package com.transitplatform.passenger.ui.main

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ConfirmationNumber
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.outlined.ConfirmationNumber
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.transitplatform.passenger.data.local.HistoryStore
import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.repository.CityRepository
import com.transitplatform.passenger.repository.FareRepository
import com.transitplatform.passenger.repository.LocationRepository
import com.transitplatform.passenger.repository.ServiceRepository
import com.transitplatform.passenger.repository.StopRepository
import com.transitplatform.passenger.ui.history.HistoryScreen
import com.transitplatform.passenger.ui.history.HistoryViewModel
import com.transitplatform.passenger.ui.history.HistoryViewModelFactory
import com.transitplatform.passenger.ui.home.HomeScreen
import com.transitplatform.passenger.ui.home.HomeViewModel
import com.transitplatform.passenger.ui.home.HomeViewModelFactory
import com.transitplatform.passenger.ui.more.MoreScreen
import com.transitplatform.passenger.ui.plan.PlanTripScreen
import com.transitplatform.passenger.ui.plan.PlanTripViewModel
import com.transitplatform.passenger.ui.plan.PlanTripViewModelFactory
import com.transitplatform.passenger.ui.theme.BorderLight
import com.transitplatform.passenger.ui.theme.GoBusBlue
import com.transitplatform.passenger.ui.theme.GoBusBlueLight
import com.transitplatform.passenger.ui.theme.TextMuted
import kotlinx.coroutines.launch

sealed class BottomNavRoute(
    val route: String,
    val title: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
) {
    object Home : BottomNavRoute("home_tab", "Home", Icons.Filled.Home, Icons.Outlined.Home)
    object History : BottomNavRoute("history_tab", "History", Icons.Default.Schedule, Icons.Outlined.Schedule)
    object MyTrips : BottomNavRoute("my_trips_tab", "My Trips", Icons.Default.ConfirmationNumber, Icons.Outlined.ConfirmationNumber)
    object More : BottomNavRoute("more_tab", "More", Icons.Default.Menu, Icons.Default.Menu)
}

val bottomNavItems = listOf(
    BottomNavRoute.Home,
    BottomNavRoute.History,
    BottomNavRoute.MyTrips,
    BottomNavRoute.More
)

@Composable
fun MainScreen(
    organizationId: String,
    cityRepository: CityRepository,
    stopRepository: StopRepository,
    locationRepository: LocationRepository,
    serviceRepository: ServiceRepository,
    fareRepository: FareRepository,
    historyStore: HistoryStore,
    rootNavController: NavHostController,
    onLogout: () -> Unit,
    onChangeCity: () -> Unit
) {
    val bottomNavController = rememberNavController()
    val navBackStackEntry by bottomNavController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route ?: BottomNavRoute.Home.route
    val currentCityName by cityRepository.getSelectedCityNameFlow().collectAsStateWithLifecycle(initialValue = null)

    Scaffold(
        contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0, 0, 0, 0),
        bottomBar = {
            NavigationBar(
                containerColor = Color.White,
                tonalElevation = 8.dp,
                modifier = Modifier.border(width = 1.dp, color = BorderLight)
            ) {
                bottomNavItems.forEach { item ->
                    val isSelected = currentRoute == item.route
                    NavigationBarItem(
                        icon = {
                            Icon(
                                imageVector = if (isSelected) item.selectedIcon else item.unselectedIcon,
                                contentDescription = item.title,
                                modifier = Modifier.size(24.dp)
                            )
                        },
                        label = {
                            Text(
                                text = item.title,
                                style = MaterialTheme.typography.labelSmall,
                                fontSize = 11.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                            )
                        },
                        selected = isSelected,
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = GoBusBlue,
                            selectedTextColor = GoBusBlue,
                            indicatorColor = GoBusBlueLight,
                            unselectedIconColor = TextMuted,
                            unselectedTextColor = TextMuted
                        ),
                        onClick = {
                            if (currentRoute != item.route) {
                                bottomNavController.navigate(item.route) {
                                    popUpTo(bottomNavController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = bottomNavController,
            startDestination = BottomNavRoute.Home.route,
            modifier = Modifier.padding(bottom = innerPadding.calculateBottomPadding())
        ) {
            // TAB 1: Home
            composable(BottomNavRoute.Home.route) {
                val homeViewModel: HomeViewModel = viewModel(
                    factory = HomeViewModelFactory(
                        cityRepository = cityRepository,
                        stopRepository = stopRepository,
                        locationRepository = locationRepository,
                        serviceRepository = serviceRepository
                    )
                )
                val scope = rememberCoroutineScope()
                
                HomeScreen(
                    viewModel = homeViewModel,
                    onLogout = onLogout,
                    onChangeCity = onChangeCity,
                    onSearchNearby = { origin, destination ->
                        scope.launch {
                            historyStore.addTrip(organizationId, origin, destination)
                        }
                        val oName = android.net.Uri.encode(origin.name)
                        val dName = android.net.Uri.encode(destination.name)
                        rootNavController.navigate("nearby_buses/${origin.id}/${destination.id}?originName=$oName&destName=$dName")
                    },
                    onSearchService = {
                        rootNavController.navigate("service_search")
                    },
                    onPlanTrip = {
                        bottomNavController.navigate(BottomNavRoute.MyTrips.route) {
                            popUpTo(bottomNavController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                )
            }

            // TAB 2: History
            composable(BottomNavRoute.History.route) {
                val historyViewModel: HistoryViewModel = viewModel(
                    factory = HistoryViewModelFactory(historyStore, organizationId)
                )
                HistoryScreen(
                    viewModel = historyViewModel,
                    onPlanTripClick = {
                        bottomNavController.navigate(BottomNavRoute.MyTrips.route) {
                            popUpTo(bottomNavController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onHistoryItemClick = { historyItem ->
                        val origin = historyItem.origin
                        val dest = historyItem.destination
                        val oName = android.net.Uri.encode(origin.name)
                        val dName = android.net.Uri.encode(dest.name)
                        rootNavController.navigate("nearby_buses/${origin.id}/${dest.id}?originName=$oName&destName=$dName")
                    }
                )
            }

            // TAB 3: My Trips (Mapped to closest valid feature: PlanTripScreen)
            composable(BottomNavRoute.MyTrips.route) {
                val planViewModel: PlanTripViewModel = viewModel(
                    factory = PlanTripViewModelFactory(serviceRepository, stopRepository, fareRepository, organizationId)
                )
                PlanTripScreen(
                    viewModel = planViewModel,
                    onBack = {
                        bottomNavController.navigate(BottomNavRoute.Home.route) {
                            popUpTo(bottomNavController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onNavigateToResults = {
                        rootNavController.navigate("plan_trip_results")
                    }
                )
            }

            // TAB 4: More (User, Active City, Change City, Logout, App Info)
            composable(BottomNavRoute.More.route) {
                MoreScreen(
                    cityName = currentCityName,
                    onChangeCity = onChangeCity,
                    onLogout = onLogout,
                    modifier = Modifier.fillMaxSize()
                )
            }
        }
    }
}
