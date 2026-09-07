# Passenger Mobile App Architecture Audit

## 1. Current Architecture Overview

The Transit Platform currently consists of:
1. **Backend** (`backend/`): Python/FastAPI providing frozen Build 3 intelligence (ETAs, tracking, dwell) and complete Passenger APIs.
2. **Operator App** (`apps/android/`): Native Android app (Kotlin + Jetpack Compose) serving as the robust tracking source.
3. **Admin Web** (`apps/admin-web/`): Internal dashboard.
4. **Passenger Web** (`apps/passenger-web/`): A React/Vite web application that serves as the UX/prototype for the passenger experience, but is not the final deployable passenger client.

## 2. Existing Android Architecture (Operator)

- **Language & UI:** Kotlin 2.1.0, Jetpack Compose, Material 3.
- **Architecture:** MVVM using ViewModel, Coroutines, and StateFlow.
- **Persistence:** Room SQLite (`TrackingPacketEntity`, etc.).
- **Networking:** OkHttp (no Retrofit abstraction, manual JSON parsing via `org.json`).
- **Background Tasks:** WorkManager (`CrowdingSyncWorker`, `TelemetrySyncWorker`) and Foreground Services (`ForegroundTrackingService`).
- **Dependencies:** Standard AndroidX, no complex Map SDK currently installed.
- **Build:** Standard single-module Gradle (`com.android.application`).

The Operator app is highly specialized for foreground/background GPS telemetry collection. It operates under strict permissions (`ACCESS_FINE_LOCATION`, `FOREGROUND_SERVICE_LOCATION`).

## 3. Passenger-Web Prototype Status

The `apps/passenger-web` directory contains a fully functional React prototype mapping to the required UX.

**Classification:**
- **A. Reusable Technically:** Low (0% for native Android UI). TypeScript API schemas and state machine logic could be loosely ported, but direct code reuse is minimal if moving to Kotlin.
- **B. Reusable Conceptually/UX-wise:** 100%. The flows (City Selection -> Home -> Destination Search -> Nearby -> Live Map; Service Search -> Details -> Departures -> Live Map) are validated and correctly orchestrate the backend APIs.
- **C. Must be rebuilt for mobile:** The entire UI layer (DOM to Native), Routing (React Router to Navigation Compose), Maps (Leaflet to Native Maps), and Storage (localStorage to DataStore).

## 4. Mobile Architecture Options

### Option A: Separate Android Application (`apps/passenger-android`)
- **Pros:** 
  - **Operator Safety:** 100% isolation. Zero risk of breaking Build 3 tracking.
  - **Permissions:** Passenger app won't inherit invasive background location permissions required by the Operator app.
  - **Deployment:** Independent versioning, QA, and Play Store releases.
  - **App Size:** Leaner passenger app without Operator telemetry libraries.
- **Cons:** 
  - Duplication of basic networking setup and API models.

### Option B: Shared Infrastructure (Multi-module)
- **Pros:** High code reuse for networking and tokens.
- **Cons:** Requires heavily refactoring the existing `apps/android` into `core`, `operator`, and `passenger` Gradle modules. **This violates the constraint to keep Build 3 frozen and safe**, introducing massive refactoring risk to the Operator app.

### Option C: Unified Application (Single APK)
- **Pros:** None functionally.
- **Cons:** Bloated app size, conflicting permissions (background location scares passengers), extreme risk of breaking Operator telemetry state.

## 5. Recommended Final Structure

**Recommendation:** Proceed with **Option A (Separate Android Application)**.

To prioritize **Operator Safety** and **Build 3 stability**, the Passenger app must be physically isolated. The cost of duplicating API models is trivial compared to the risk of destabilizing the Operator telemetry engine.

```
apps/
├── android/              ← Operator App (Frozen / Stable)
├── passenger-android/    ← Passenger App (NEW)
├── admin-web/            ← Admin Dashboard
└── passenger-web/        ← Prototype / Reference UX
```

*Note on iOS:* If future iOS support is heavily prioritized, building `apps/passenger-app` using React Native (reusing `passenger-web` logic) or Kotlin Multiplatform (KMP) is viable. However, given the existing Kotlin/Compose stack, a native `passenger-android` provides the highest fidelity Android UX.

## 6. Shared Code Strategy

**Recommendation:** **No shared code modules.**
To guarantee Operator isolation, do not extract a shared Android `core` module. 
- API models for Passenger and Operator are completely different (Telemetry vs ETAs).
- Network clients can be easily duplicated or rewritten using Retrofit for the passenger app.
- Shared code should be limited to "copy-pasting" the design token hexadecimal values and generic utilities, maintaining strict build isolation.

## 7. Map Strategy

**Recommendation:** **Google Maps SDK for Android (`maps-compose`)**
- **Why:** The prototype uses Leaflet, which is web-only. For native Android Compose, `com.google.maps.android:maps-compose` is the industry standard. It natively supports the required route polylines, custom stop markers, live bus markers (with bearing/heading rotation), and smooth gestures without webview overhead.

## 8. Mobile Storage Strategy

**Recommendation:** **Jetpack DataStore + EncryptedSharedPreferences**
- **Auth Token:** `EncryptedSharedPreferences` (or Android Keystore backed) for securely storing the JWT `access_token`.
- **Selected City & History:** `Preferences DataStore` to replace `localStorage` for primitive persistent state (e.g., `city_id`, recent searches).

## 9. Backend Contract Readiness

All required APIs are production-ready for the mobile client. No backend modifications are needed.
- `POST /api/auth/passenger/login` (Auth)
- `GET /api/passenger/organizations` (City Selection)
- `GET /api/passenger/stops` (Search)
- `GET /api/passenger/services` (Search)
- `GET /api/passenger/services/search` (Destination Nearby)
- `GET /api/passenger/services/{id}` (Details)
- `GET /api/passenger/stops/{id}/departures` (Schedule)
- `GET /api/passenger/services/{id}/live` (Live Map)

## 10. Explicitly Untouched Boundaries

The following components **must remain strictly untouched**:
1. `backend/app/services/intelligence/` (All Build 3 Engines: ETA, Direction, Dwell, Fusion, Progression).
2. `apps/android/` (Operator Tracking, WorkManagers, Foreground Services).
3. Backend Database schemas and migrations.
4. Fare algorithms or Major Depot schemas.

## 11. Migration & Implementation Sequence

The implementation of `apps/passenger-android` should follow this controlled sequence:

1. **Foundation:** Initialize `apps/passenger-android` as a modern Jetpack Compose project (Retrofit, DataStore, Hilt/Koin).
2. **Design System:** Implement GoBus Blue theme, typography, and reusable Compose UI components.
3. **Auth & City:** Implement Login Screen, JWT persistence, and City Selection.
4. **Home & Search:** Implement Home screen, floating UI, and Destination search UI.
5. **Nearby Services:** Integrate `/api/passenger/services/search` and render ServiceResultCards.
6. **Live Map (Core UX):** Integrate Google Maps SDK, render route polylines, stops, and live bus markers with rotation.
7. **Service Information:** Implement Service Search, Service Details, and Departure Boards.
8. **Ancillary:** History and Plan Trip.
9. **Polish & Release:** Transitions, error handling, offline caching, and release build configuration.

## 12. Next Exact Implementation Step

**Action:** Initialize the `apps/passenger-android` project.
Specifically: Create the root Android project structure, configure Gradle (Compose, Retrofit, Kotlin serialization), and establish the base `MainActivity` and `Theme` without altering any existing repository code.
