package com.transitplatform.passenger.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.transitplatform.passenger.data.model.PassengerServiceSearchResponse
import com.transitplatform.passenger.repository.FareRepository
import com.transitplatform.passenger.repository.ServiceRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

enum class EmptyReason {
    NO_SERVICES_FOUND,
    NO_MORE_BUSES_TODAY,
    FILTER_NO_MATCH
}

sealed class NearbyBusResultsUiState {
    object Loading : NearbyBusResultsUiState()
    data class Success(
        val allResults: List<SearchResultItemUiModel>,
        val displayedResults: List<SearchResultItemUiModel>,
        val totalBusesFound: Int,
        val totalBusesEnRoute: Int,
        val selectedFilter: SearchFilter,
        val selectedSort: SearchSort,
        val searchDateDisplay: String,
        val rawDate: String,
        val isToday: Boolean,
        val currentOriginName: String,
        val currentDestName: String,
        val currentOriginId: String,
        val currentDestId: String
    ) : NearbyBusResultsUiState()
    data class Empty(
        val reason: EmptyReason,
        val currentOriginName: String,
        val currentDestName: String,
        val searchDateDisplay: String
    ) : NearbyBusResultsUiState()
    data class Error(val message: String) : NearbyBusResultsUiState()
}

class NearbyBusViewModel(
    private val serviceRepository: ServiceRepository,
    private val fareRepository: FareRepository,
    private val organizationId: String,
    private val initialOriginId: String,
    private val initialDestinationId: String,
    private val initialOriginName: String,
    private val initialDestName: String,
    private val initialDateMillis: Long? = null,
    private val initialFilterStr: String? = null,
    private val externalScope: kotlinx.coroutines.CoroutineScope? = null
) : ViewModel() {

    private val scope: kotlinx.coroutines.CoroutineScope
        get() = externalScope ?: viewModelScope

    private val _state = MutableStateFlow<NearbyBusResultsUiState>(NearbyBusResultsUiState.Loading)
    val state: StateFlow<NearbyBusResultsUiState> = _state.asStateFlow()

    var currentOriginId = initialOriginId
        private set
    var currentDestId = initialDestinationId
        private set
    var currentOriginName = initialOriginName
        private set
    var currentDestName = initialDestName
        private set

    private val kolkataTimeZone = TimeZone.getTimeZone("Asia/Kolkata")
    private var selectedCalendar: Calendar = Calendar.getInstance(kolkataTimeZone)
    private var selectedFilter: SearchFilter = SearchFilter.ALL_BUSES
    private var selectedSort: SearchSort = SearchSort.BEST_MATCH

    private var cachedAllResults: List<SearchResultItemUiModel> = emptyList()

    init {
        if (initialDateMillis != null && initialDateMillis > 0) {
            selectedCalendar.timeInMillis = initialDateMillis
        }
        if (!initialFilterStr.isNullOrBlank()) {
            when (initialFilterStr.uppercase(Locale.ROOT)) {
                "AC" -> selectedFilter = SearchFilter.AC
                "NON_AC" -> selectedFilter = SearchFilter.NON_AC
                "DIRECT" -> selectedFilter = SearchFilter.DIRECT
                "LOWEST_PRICE" -> selectedSort = SearchSort.LOWEST_PRICE
                "QUICKEST" -> selectedSort = SearchSort.QUICKEST
            }
        }
        searchServices()
    }

    fun searchServices(): kotlinx.coroutines.Job {
        _state.value = NearbyBusResultsUiState.Loading
        return scope.launch {
            val isToday = isSelectedCalendarToday(selectedCalendar)
            val dateStr = formatRawDate(selectedCalendar)
            val timeFmt = SimpleDateFormat("HH:mm:ss", Locale.US).apply { timeZone = kolkataTimeZone }
            val timeStr = timeFmt.format(selectedCalendar.time)

            val searchResult = serviceRepository.searchServices(
                organizationId = organizationId,
                originId = currentOriginId,
                destinationId = currentDestId,
                searchDate = dateStr,
                searchTime = timeStr,
                sortBy = selectedSort.name,
                filterBy = "ALL"
            )
            searchResult.fold(
                onSuccess = { candidateServices ->
                    if (candidateServices.isEmpty()) {
                        cachedAllResults = emptyList()
                        _state.value = NearbyBusResultsUiState.Empty(
                            reason = EmptyReason.NO_SERVICES_FOUND,
                            currentOriginName = currentOriginName,
                            currentDestName = currentDestName,
                            searchDateDisplay = formatDateDisplay(selectedCalendar)
                        )
                        return@launch
                    }

                    val uiModels = candidateServices.map { mapCandidate(it, isToday) }
                    val availableResults = uiModels.filter { it.availabilityMode != AvailabilityMode.UNAVAILABLE }

                    if (availableResults.isEmpty()) {
                        cachedAllResults = emptyList()
                        _state.value = NearbyBusResultsUiState.Empty(
                            reason = if (isToday) EmptyReason.NO_MORE_BUSES_TODAY else EmptyReason.NO_SERVICES_FOUND,
                            currentOriginName = currentOriginName,
                            currentDestName = currentDestName,
                            searchDateDisplay = formatDateDisplay(selectedCalendar)
                        )
                        return@launch
                    }

                    val validFares = availableResults.mapNotNull { it.fareAmount }
                    val minFare = validFares.minOrNull()

                    val validDurations = availableResults.map { it.journeyDurationSeconds }
                    val minDuration = validDurations.minOrNull()

                    val finalizedResults = availableResults.mapIndexed { index, item ->
                        item.copy(
                            isBestMatch = (index == 0),
                            isLowestPrice = (minFare != null && item.fareAmount == minFare),
                            isQuickest = (minDuration != null && item.journeyDurationSeconds == minDuration)
                        )
                    }

                    cachedAllResults = finalizedResults
                    updateSuccessState()
                },
                onFailure = { error ->
                    _state.value = NearbyBusResultsUiState.Error(
                        "Unable to load buses right now. Please check your connection and try again."
                    )
                }
            )
        }
    }

    private fun mapCandidate(
        candidate: PassengerServiceSearchResponse,
        isToday: Boolean
    ): SearchResultItemUiModel {
        val availMode = when (candidate.availability_mode.uppercase(Locale.ROOT)) {
            "LIVE" -> AvailabilityMode.LIVE
            "SCHEDULED" -> AvailabilityMode.SCHEDULED
            else -> AvailabilityMode.UNAVAILABLE
        }
        val depMode = when (candidate.departure_mode.uppercase(Locale.ROOT)) {
            "LIVE_DEPARTURE" -> DepartureMode.LIVE_DEPARTURE
            else -> DepartureMode.SCHEDULED_DEPARTURE
        }
        val arrMode = when (candidate.arrival_mode.uppercase(Locale.ROOT)) {
            "LIVE_ETA" -> ArrivalMode.LIVE_ETA
            else -> ArrivalMode.SCHEDULED_ARRIVAL
        }

        val depMillis = candidate.departure_timestamp?.let { parseIsoToMillis(it) }
        val arrMillis = candidate.arrival_timestamp?.let { parseIsoToMillis(it) }
        val expArrMillis = candidate.expected_arrival_timestamp?.let { parseIsoToMillis(it) }

        val depTimeFormatted = if (depMillis != null) formatTimeFromMillis(depMillis) else "--"
        val arrTimeFormatted = if (arrMillis != null) formatTimeFromMillis(arrMillis) else "--"

        val depLabel = if (availMode == AvailabilityMode.LIVE) {
            candidate.relative_message ?: "Arriving soon"
        } else {
            candidate.relative_message ?: "Next departure"
        }

        val arrLabel = if (availMode == AvailabilityMode.LIVE) "Expected arrival" else "Scheduled arrival"

        val durationSec = candidate.journey_duration_seconds ?: 600
        val durationMin = kotlin.math.max(1, (durationSec + 30) / 60)

        val crowdDisplay = candidate.nearest_bus?.crowd_level?.replace("_", " ")

        return SearchResultItemUiModel(
            serviceId = candidate.service_id,
            serviceName = candidate.service_name,
            serviceCode = candidate.service_code,
            direction = candidate.direction,
            absoluteOrigin = candidate.absolute_origin ?: currentOriginName,
            absoluteDestination = candidate.absolute_destination ?: currentDestName,
            searchedOrigin = candidate.searched_origin ?: currentOriginName,
            searchedDestination = candidate.searched_destination ?: currentDestName,
            departureTimeFormatted = depTimeFormatted,
            arrivalTimeFormatted = arrTimeFormatted,
            departureLabel = depLabel,
            arrivalLabel = arrLabel,
            departureTimestampMillis = depMillis,
            arrivalTimestampMillis = arrMillis,
            expectedArrivalTimestampMillis = expArrMillis,
            relativeWaitSeconds = candidate.relative_wait_seconds,
            relativeMessage = candidate.relative_message,
            availabilityMode = availMode,
            departureMode = depMode,
            arrivalMode = arrMode,
            durationMinutes = durationMin,
            journeyDurationSeconds = durationSec,
            stopsCount = candidate.stops_count,
            fareAmount = candidate.fare,
            currency = "₹",
            isAc = candidate.is_ac,
            isDirect = candidate.is_direct,
            crowdLevel = crowdDisplay,
            activeBusesCount = if (isToday) candidate.active_buses_count else 0,
            nearestBusEtaSeconds = if (isToday) candidate.nearest_bus?.eta_seconds else null,
            nearestBusEtaMinutes = if (isToday) candidate.nearest_bus?.eta_seconds?.let { kotlin.math.max(0, it / 60) } else null,
            isBestMatch = false,
            isLowestPrice = false,
            isQuickest = false,
            rankingScore = candidate.ranking_score
        )
    }

    fun setFilter(filter: SearchFilter) {
        selectedFilter = filter
        updateSuccessState()
    }

    fun setSort(sort: SearchSort) {
        selectedSort = sort
        updateSuccessState()
    }

    fun clearFilters() {
        selectedFilter = SearchFilter.ALL_BUSES
        selectedSort = SearchSort.BEST_MATCH
        updateSuccessState()
    }

    fun swapStops(): kotlinx.coroutines.Job {
        val tempId = currentOriginId
        val tempName = currentOriginName
        currentOriginId = currentDestId
        currentOriginName = currentDestName
        currentDestId = tempId
        currentDestName = tempName

        cachedAllResults = emptyList()
        return searchServices()
    }

    fun setDate(year: Int, month: Int, dayOfMonth: Int): kotlinx.coroutines.Job {
        selectedCalendar.set(Calendar.YEAR, year)
        selectedCalendar.set(Calendar.MONTH, month)
        selectedCalendar.set(Calendar.DAY_OF_MONTH, dayOfMonth)

        cachedAllResults = emptyList()
        return searchServices()
    }

    fun setTime(hourOfDay: Int, minute: Int): kotlinx.coroutines.Job {
        selectedCalendar.set(Calendar.HOUR_OF_DAY, hourOfDay)
        selectedCalendar.set(Calendar.MINUTE, minute)
        selectedCalendar.set(Calendar.SECOND, 0)

        cachedAllResults = emptyList()
        return searchServices()
    }

    private fun updateSuccessState() {
        if (cachedAllResults.isEmpty()) {
            return
        }

        var list = cachedAllResults

        // Apply Filter
        list = when (selectedFilter) {
            SearchFilter.ALL_BUSES -> list
            SearchFilter.AC -> list.filter { it.isAc }
            SearchFilter.NON_AC -> list.filter { !it.isAc }
            SearchFilter.DIRECT -> list.filter { it.isDirect }
        }

        if (list.isEmpty()) {
            _state.value = NearbyBusResultsUiState.Empty(
                reason = EmptyReason.FILTER_NO_MATCH,
                currentOriginName = currentOriginName,
                currentDestName = currentDestName,
                searchDateDisplay = formatDateDisplay(selectedCalendar)
            )
            return
        }

        // Apply Sort
        list = when (selectedSort) {
            SearchSort.BEST_MATCH -> {
                val orderMap = cachedAllResults.mapIndexed { idx, it -> it.serviceId to idx }.toMap()
                list.sortedBy { orderMap[it.serviceId] ?: 999 }
            }
            SearchSort.LOWEST_PRICE -> list.sortedBy { it.fareAmount ?: Double.MAX_VALUE }
            SearchSort.QUICKEST -> list.sortedWith(
                compareBy<SearchResultItemUiModel> { it.journeyDurationSeconds }
                    .thenBy { it.arrivalTimestampMillis ?: Long.MAX_VALUE }
            )
            SearchSort.EARLIEST_DEPARTURE -> list.sortedBy { it.departureTimestampMillis ?: Long.MAX_VALUE }
        }

        val isToday = isSelectedCalendarToday(selectedCalendar)
        val totalEnRoute = if (isToday) list.sumOf { it.activeBusesCount } else 0

        _state.value = NearbyBusResultsUiState.Success(
            allResults = cachedAllResults,
            displayedResults = list,
            totalBusesFound = list.size,
            totalBusesEnRoute = totalEnRoute,
            selectedFilter = selectedFilter,
            selectedSort = selectedSort,
            searchDateDisplay = formatDateDisplay(selectedCalendar),
            rawDate = formatRawDate(selectedCalendar),
            isToday = isToday,
            currentOriginName = currentOriginName,
            currentDestName = currentDestName,
            currentOriginId = currentOriginId,
            currentDestId = currentDestId
        )
    }

    private fun isSelectedCalendarToday(calendar: Calendar): Boolean {
        val today = Calendar.getInstance(kolkataTimeZone)
        return today.get(Calendar.YEAR) == calendar.get(Calendar.YEAR) &&
                today.get(Calendar.DAY_OF_YEAR) == calendar.get(Calendar.DAY_OF_YEAR)
    }

    private fun formatDateDisplay(calendar: Calendar): String {
        val isToday = isSelectedCalendarToday(calendar)
        val dateFmt = SimpleDateFormat("d MMM yyyy", Locale.US)
        dateFmt.timeZone = kolkataTimeZone
        val formattedDate = dateFmt.format(calendar.time)
        return if (isToday) "Today, $formattedDate" else formattedDate
    }

    private fun formatRawDate(calendar: Calendar): String {
        val fmt = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        fmt.timeZone = kolkataTimeZone
        return fmt.format(calendar.time)
    }

    private fun formatIsoTimeToDisplay(iso: String?): String {
        if (iso == null) return "--"
        return try {
            val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            parser.timeZone = TimeZone.getTimeZone("UTC")
            val cleanIso = if (iso.contains(".")) iso.substringBefore(".") else iso.replace("Z", "")
            val date = parser.parse(cleanIso) ?: return iso
            val displayFmt = SimpleDateFormat("h:mm a", Locale.US)
            displayFmt.timeZone = kolkataTimeZone
            displayFmt.format(date).lowercase(Locale.US)
        } catch (e: Exception) {
            iso
        }
    }

    private fun formatTimeFromMillis(millis: Long?): String {
        if (millis == null) return "--"
        val fmt = SimpleDateFormat("h:mm a", Locale.US)
        fmt.timeZone = kolkataTimeZone
        return fmt.format(Date(millis)).lowercase(Locale.US)
    }

    private fun parseIsoToMillis(iso: String?): Long {
        if (iso == null) return System.currentTimeMillis()
        return try {
            val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            parser.timeZone = TimeZone.getTimeZone("UTC")
            val cleanIso = if (iso.contains(".")) iso.substringBefore(".") else iso.replace("Z", "")
            parser.parse(cleanIso)?.time ?: System.currentTimeMillis()
        } catch (e: Exception) {
            System.currentTimeMillis()
        }
    }
}

class NearbyBusViewModelFactory(
    private val serviceRepository: ServiceRepository,
    private val fareRepository: FareRepository,
    private val organizationId: String,
    private val originId: String,
    private val destinationId: String,
    private val originName: String,
    private val destinationName: String,
    private val initialDateMillis: Long? = null,
    private val initialFilterStr: String? = null
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(NearbyBusViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return NearbyBusViewModel(
                serviceRepository = serviceRepository,
                fareRepository = fareRepository,
                organizationId = organizationId,
                initialOriginId = originId,
                initialDestinationId = destinationId,
                initialOriginName = originName,
                initialDestName = destinationName,
                initialDateMillis = initialDateMillis,
                initialFilterStr = initialFilterStr
            ) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
    }
}
