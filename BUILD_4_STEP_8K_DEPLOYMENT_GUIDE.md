# GoBus Transit Platform — Deployment Guide

This guide describes how to deploy the GoBus platform for the SIH presentation.

## A. Development Setup
For local development:
1. Clone the repository.
2. Run `docker-compose up -d db` to start the local database.
3. In `backend/`, run `pip install -e .` and `uvicorn app.main:app --reload`.
4. In `apps/admin-web/`, run `npm install` and `npm run dev`.

## B. Demo / Staging Setup (SIH Environment)
The SIH demo environment requires all components running on a single Demo PC, with Android devices connecting over the local area network (LAN).
1. Identify the Demo PC's LAN IP Address (e.g. `192.168.1.100`).
2. Copy `.env.demo.example` to `.env`.
3. Update `CORS_ORIGINS` in `.env` to include your Demo PC IP: `http://192.168.1.100`.
4. Run `docker-compose -f docker-compose.demo.yml up -d --build`.
   This will spin up the database, the FastAPI backend, and a Caddy reverse proxy serving the Admin Web on port 80.

## C. Environment Variables
Never commit real secrets.
Create `.env` using `.env.demo.example` as a template.
- `APP_ENV=demo`
- `JWT_SECRET=secure_random_string`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=your_password`

## D. Database Creation & E. PostGIS Requirement
The `docker-compose.demo.yml` file uses the `postgis/postgis:16-3.4` image, which automatically provides the PostGIS extension. No manual database creation is required.

## F. Alembic Migration
To initialize the database schema on the Demo PC:
```bash
docker exec -it demo-transit-api alembic upgrade head
```
*(Optional) If you want to seed development data:*
```bash
docker exec -it demo-transit-api python -m app.db.seed
```

## G. Admin Web Deployment
Admin Web is statically built into `/usr/share/caddy` and served by Caddy. Caddy handles the `/api` routing to the backend. Open `http://<DEMO-PC-IP>` in your browser.

## H. Backend Deployment
The backend runs a single Uvicorn worker inside the `api` container. This is intentional to ensure only a single instance of `AlertEngine` runs concurrently. It is only accessible via the Caddy reverse proxy on `/api`.

## I. Android DEMO Configuration
Android apps use `local.properties` or environment variables to inject the backend URL.
1. Create `local.properties` in the root of the Android project (`apps/passenger-android/` and `apps/android/`).
2. Add: `DEBUG_BASE_URL=http://<DEMO-PC-IP>`
   (e.g., `DEBUG_BASE_URL=http://192.168.1.100`)
3. **Note:** Android's `network_security_config.xml` allows HTTP cleartext *only* for typical local IP addresses (like `192.168.*.*`, `10.*.*.*`).

## J. Passenger APK Build
Navigate to `apps/passenger-android` and run:
```bash
./gradlew assembleDebug
```
Install the generated APK (`app/build/outputs/apk/debug/app-debug.apk`) on the Passenger physical device.

## K. Operator APK Build
Navigate to `apps/android` and run:
```bash
./gradlew assembleDebug
```
Install the generated APK on the Operator physical device.

## L. Backend Health Verification
```bash
curl http://<DEMO-PC-IP>/api/health/db
```
Should return `{"status":"ok","database":"connected"}`.

## M. Admin Web Verification
Navigate to `http://<DEMO-PC-IP>` on any laptop connected to the same LAN. Log in using `fleet@demo.com` and `operator123`.

## N. Database Backup
```bash
docker exec -it demo-transit-db pg_dump -U postgres -d transit_platform > backup.sql
```

## O. Database Restore
```bash
cat backup.sql | docker exec -i demo-transit-db psql -U postgres -d transit_platform
```

## P. Local Emergency Fallback
If the SIH venue has strict Wi-Fi isolation and devices cannot communicate over the LAN, you must use a local Android emulator or a physical USB tethering bridge. The local fallback `docker-compose.yml` remains identical to `docker-compose.demo.yml` but without exposing Caddy to external IPs (use `127.0.0.1` instead).

## Q. Troubleshooting
- **Android App crashes/fails to connect:** Ensure `DEBUG_BASE_URL` in `local.properties` does NOT have a trailing slash (e.g. `http://192.168.1.100` is correct).
- **CORS Errors:** Ensure the IP address you type in the browser EXACTLY matches the IP in `CORS_ORIGINS` in `.env`.
