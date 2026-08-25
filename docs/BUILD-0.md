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

## Checks

| Check | Command | Expected |
|-------|---------|----------|
| Backend health | `curl http://localhost:8000/health` | `{"status":"ok","service":"transit-backend"}` |
| DB health | `curl http://localhost:8000/health/db` | `{"status":"ok","database":"connected"}` |
| Backend tests | `cd backend && pytest` | All pass |
| Backend lint | `cd backend && ruff check app/` | Clean |
| Web build | `cd apps/admin-web && npm run build` | Success |
| Web types | `cd apps/admin-web && npx tsc --noEmit` | Clean |
| Android build | `cd apps/android && ./gradlew assembleDebug` | Success |

## Acceptance Criteria

See specification Section 27 for the full acceptance checklist.

## Known Limitations

- BUILD 0 contains zero product features by design
- Empty architectural directories exist as structural boundaries
- No domain database tables or migrations
- No authentication (JWT_SECRET is config preparation only)
- Intelligence module is documentation-only
