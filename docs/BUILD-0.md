# BUILD 0 — Foundation

## Scope

BUILD 0 establishes a healthy, reproducible monorepo foundation for
the Intelligent Transit Platform. It contains **no product features**.

## Architecture Boundary

BUILD 0 includes:
- ✅ Monorepo structure
- ✅ FastAPI backend with health endpoints
- ✅ PostgreSQL/PostGIS infrastructure (Docker Compose)
- ✅ SQLAlchemy connection infrastructure
- ✅ Alembic migration framework (configured, no domain migrations)
- ✅ Vite + React + TypeScript admin web scaffold
- ✅ Android Kotlin + Jetpack Compose project scaffold
- ✅ Logging foundation
- ✅ Environment configuration
- ✅ Testing foundation

BUILD 0 does NOT include:
- ❌ Domain models or database tables
- ❌ Product APIs
- ❌ Authentication / authorization
- ❌ GPS tracking / location services
- ❌ ETA predictions
- ❌ Business logic of any kind
- ❌ Seed data
- ❌ WebSocket
- ❌ External service integrations

## Commands

### Infrastructure
```bash
# Start PostgreSQL/PostGIS
docker compose up -d

# Stop infrastructure
docker compose down

# View logs
docker compose logs -f
```

### Backend
```bash
cd backend

# Create virtual environment & install
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run linter
ruff check app/
```

### Admin Web
```bash
cd apps/admin-web

# Install dependencies
npm install

# Start development server
npm run dev

# Production build
npm run build

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

### Android
```bash
cd apps/android

# Build debug APK
./gradlew assembleDebug

# Run tests
./gradlew test

# Run lint checks
./gradlew lint
```

## Checks & Verification Results

| Check | Command | Status | Result |
|---|---|---|---|
| PostgreSQL & PostGIS | `docker compose ps` | **PASS** | Up 2 hours (healthy), PostGIS 3.4 active |
| Backend Health | Direct / live testclient | **PASS** | `{"status":"ok","service":"transit-backend"}` |
| DB Health | Direct / live testclient | **PASS** | `{"status":"ok","database":"connected"}` |
| Backend Tests | `cd backend && pytest` | **PASS** | 4/4 passed in 1.61s |
| Backend Lint | `cd backend && ruff check app/ tests/` | **PASS** | All checks passed |
| Alembic Tooling | `cd backend && alembic current` | **PASS** | PostgresqlImpl connected |
| Web Build | `cd apps/admin-web && npm run build` | **PASS** | dist/ generated in 1.18s |
| Web Types | `cd apps/admin-web && npx tsc -b` | **PASS** | 0 errors |
| Web Lint | `cd apps/admin-web && npm run lint` | **PASS** | 0 warnings, 0 errors |
| Android Gradle Wrapper | `cd apps/android && gradlew.bat --version` | **PASS** | Gradle 8.11.1, JVM 17 |
| Android Gradle Tasks | `cd apps/android && gradlew.bat tasks` | **PASS** | BUILD SUCCESSFUL |
| Android Assemble Debug | `cd apps/android && gradlew.bat assembleDebug` | **PASS** | BUILD SUCCESSFUL (app-debug.apk 9.4MB) |
| Android Tests | `cd apps/android && gradlew.bat test` | **PASS** | BUILD SUCCESSFUL (unit tests passed) |
| Physical Device Detection | `adb devices -l` | **PASS** | Detected SM-A556E (API 36) |

## Acceptance Criteria

- [x] Monorepo structure exists
- [x] Git configuration & initial checkpoint exist
- [x] README exists
- [x] BUILD 0 documentation exists
- [x] Docker starts PostgreSQL 16 with PostGIS 3.4
- [x] PostGIS extension is enabled and verified
- [x] FastAPI starts with configuration and structured logging
- [x] `/health` returns service ok
- [x] `/health/db` tests actual database connectivity
- [x] SQLAlchemy connection infrastructure works
- [x] Alembic migration framework is wired and operational
- [x] Backend tests (unit & integration) pass
- [x] Backend lint checks pass
- [x] Admin Web Vite + React + TypeScript scaffold exists
- [x] Admin Web production build succeeds
- [x] Admin Web TypeScript and lint checks pass
- [x] Android Gradle Wrapper operates with JDK 17
- [x] Android assembleDebug produces debug APK
- [x] Android unit tests pass
- [x] NO domain tables, models, migrations, seed data, or product APIs exist
- [x] Lockfiles and Gradle Wrapper committed, `.env` ignored
- [x] Documented commands verified reproducible

## Known Limitations

- BUILD 0 contains zero product features by design
- Empty architectural directories exist as structural boundaries
- No domain database tables or migrations
- No authentication (JWT_SECRET is config preparation only)
- Intelligence module is documentation-only
- Physical device test completed detection and environment validation (API 36 / SM-A556E)

