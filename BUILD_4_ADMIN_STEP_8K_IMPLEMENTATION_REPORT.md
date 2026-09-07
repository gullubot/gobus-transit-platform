# Build 4 — Step 8K: Deployment Architecture & Demonstration Hardening

**Status:** COMPLETE  
**Date:** 2026-08-31

This report summarizes the changes implemented to harden the GoBus Transit Platform for the SIH deployment environment, including establishing the local fallback behavior and configuring dynamic endpoints across Android applications.

---

## 1. Files Created
- `docker-compose.demo.yml`: Primary orchestration file for the SIH demo (DB, FastAPI, Admin Web, Caddy).
- `Caddyfile.demo`: Reverse proxy configuration serving static Admin Web assets on `/` and proxying `/api` to FastAPI.
- `.env.demo.example`: Clean template for production-like environment variables.
- `apps/admin-web/Dockerfile`: Multi-stage Docker build for the Admin Web React application.
- `apps/passenger-android/app/src/main/res/xml/network_security_config.xml`: Restricts HTTP cleartext exclusively to local/demo IP ranges.
- `apps/android/app/src/main/res/xml/network_security_config.xml`: Same restriction for the Operator app.
- `BUILD_4_STEP_8K_DEPLOYMENT_GUIDE.md`: Comprehensive end-to-end documentation for deploying and testing the SIH Demo.

## 2. Files Modified
- `backend/app/core/config.py`: Enforces explicit `JWT_SECRET` in non-development environments, throwing a startup error if the fallback is used.
- `apps/passenger-android/app/build.gradle.kts`: `BuildConfig.BASE_URL` is now dynamically injected from `local.properties` or environment variables (e.g. `DEBUG_BASE_URL`).
- `apps/passenger-android/app/src/main/AndroidManifest.xml`: Replaced global `usesCleartextTraffic="true"` with explicit `networkSecurityConfig`.
- `apps/android/app/build.gradle.kts`: Applied identical `BuildConfig.BASE_URL` dynamic injection as Passenger.
- `apps/android/app/src/main/AndroidManifest.xml`: Replaced global `usesCleartextTraffic="true"` with explicit `networkSecurityConfig`.

---

## 3. Deployment Architecture

### A. Primary Demo Architecture (SIH)
The architecture represents a unified local-cloud network strategy for the SIH presentation.
- **Demo PC (Host):** Runs `docker-compose.demo.yml` hosting:
  - PostGIS (port 5432, internal only).
  - FastAPI Backend (port 8000, internal only).
  - Admin Web Static Container (Volume share only).
  - Caddy Reverse Proxy (ports 80/443 exposed to the host machine).
- **Client Devices:** 
  - Operator Android and Passenger Android connect to the Demo PC over the LAN using the Demo PC's specific IP address.
  - Admin Web browsers connect to the Demo PC IP via `http://<DEMO-IP>`.
- **API Resolution:** Admin Web uses relative `/api` paths seamlessly proxied by Caddy, completely avoiding CORS complexities.

### B. Environment Strategy
- `APP_ENV=demo` is used for the Demo PC.
- Secrets (`POSTGRES_PASSWORD`, `JWT_SECRET`) are mandated via the `.env` file.
- `CORS_ORIGINS` is restricted specifically to the local network IP or public domain assigned.
- Development fallbacks are strictly prohibited from silently activating during Demo/Production builds.

### C. Android Configuration Strategy
- Both Android Apps (`apps/passenger-android` and `apps/android`) read `DEBUG_BASE_URL` from a `local.properties` file at build time.
- The `network_security_config.xml` enables HTTP traffic strictly for `127.0.0.1`, `10.0.2.2`, and typical LAN patterns (`192.168.x.x`), while preserving standard HTTPS validation rules for real public domains.

---

## 4. Verification Results

All automated verification commands succeeded against the newly hardened environment:

- **Backend Verification:** `alembic upgrade head && python -m pytest --tb=short -q` 
  - Result: **Passed** (335 tests passed, 0 failures. Alembic migrations successful).
- **Admin Web Verification:** `npm run lint && npm run build`
  - Result: **Passed** (Successfully compiled to static Vite assets).
- **Passenger Android Verification:** `./gradlew assembleDebug`
  - Result: **Passed** (BUILD SUCCESSFUL in 2m 3s with dynamic URL injection).
- **Operator Android Verification:** `./gradlew assembleDebug`
  - Result: **Passed** (BUILD SUCCESSFUL in 1m 54s with dynamic URL injection).

### Git Safety Audit
- **Build 3 Intelligence:** Completely untouched.
- **TrackerFusion / ETAEngine:** Untouched.
- **Fare / Alert Models:** Untouched.
- **Fake State Logic:** None introduced. The simulator environment will remain entirely external as directed.

---

## 5. Known Limitations / Pending
- **External Cloud Deployment (Optional):** We have configured the software for cloud deployment (e.g., Supabase/Railway) with environment variables. However, physical cloud deployment was not executed as external provider credentials were not requested. 
- **Recommendation:** Proceeding with the unified single-machine Demo PC (LAN approach) is heavily recommended for SIH to avoid unpredictable conference Wi-Fi latency.

BUILD_4_ADMIN_STEP_8K_IMPLEMENTATION_COMPLETE
