# Transit Platform

An intelligent public-transport platform for fragmented bus networks,
demonstrated through a small-city / tier-2/3 transport scenario.

> **BUILD 0 — Foundation Only**
> This repository contains only the development foundation.
> No product features, domain models, or business logic exist yet.

## Repository Structure

```
transit-platform/
├── apps/
│   ├── android/          # Android app (Kotlin + Jetpack Compose)
│   └── admin-web/        # Admin web app (Vite + React + TypeScript)
├── backend/              # Backend API (Python + FastAPI)
├── shared/               # Shared contracts and documentation
├── infra/                # Infrastructure configuration
├── docs/                 # Architecture and developer documentation
├── scripts/              # Development and utility scripts
├── docker-compose.yml    # Service definitions
├── .env.example          # Environment template
└── README.md             # This file
```

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| JDK | 17 (Temurin 17.0.20.1) | Android builds |
| Android SDK | Platform 35, Build Tools | Android builds |
| Python | 3.13.7 | Backend |
| Node.js | v24.14.1 | Admin web |
| npm | 11.11.0 | Admin web package management |
| Docker | 29.7.2 | Infrastructure |
| Docker Compose | v5.4.0 | Infrastructure orchestration |
| Git | 2.51.0 | Version control |

## Environment Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd transit-platform

# 2. Copy environment configuration
cp .env.example .env
# Edit .env with your local values if needed

# 3. Start infrastructure (PostgreSQL/PostGIS)
docker compose up -d

# 4. Set up backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -e ".[dev]"
cd ..

# 5. Set up admin web
cd apps/admin-web
npm install
cd ../..
```

## Infrastructure

```bash
# Start PostgreSQL/PostGIS
docker compose up -d

# Stop infrastructure
docker compose down

# View logs
docker compose logs -f

# Check database status
docker compose ps
```

## Backend

```bash
cd backend

# Activate virtual environment
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run linter
ruff check app/
```

## Admin Web

```bash
cd apps/admin-web

# Start development server
npm run dev

# Production build
npm run build

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

## Android

```bash
cd apps/android

# Build debug APK
gradlew.bat assembleDebug       # Windows
# ./gradlew assembleDebug       # Linux/macOS

# Run unit tests
gradlew.bat test

# Run lint
gradlew.bat lint
```

## Health Endpoints

Once the backend and database are running:

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /health` | Application health | `{"status": "ok", "service": "transit-backend"}` |
| `GET /health/db` | Database connectivity | `{"status": "ok", "database": "connected"}` |

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
```

## Tests & Checks

| Component | Command | Description |
|-----------|---------|-------------|
| Backend tests | `cd backend && pytest` | Unit and integration tests |
| Backend lint | `cd backend && ruff check app/` | Code style checks |
| Web build | `cd apps/admin-web && npm run build` | Production build |
| Web types | `cd apps/admin-web && npx tsc --noEmit` | TypeScript type check |
| Web lint | `cd apps/admin-web && npm run lint` | ESLint/Oxlint checks |
| Android build | `cd apps/android && gradlew.bat assembleDebug` | Debug build |
| Android test | `cd apps/android && gradlew.bat test` | Unit tests |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Android | Kotlin, Jetpack Compose, Gradle Wrapper |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL 16, PostGIS 3.4 |
| Admin Web | Vite, React, TypeScript |
| Infrastructure | Docker Compose |
| Architecture | Modular monolith |

## Known BUILD 0 Limitations

- **No product features exist** — BUILD 0 is infrastructure foundation only
- Empty architectural directories serve as structural boundaries
- No domain database tables, models, or migrations
- No authentication (JWT_SECRET is config preparation for a future build)
- No GPS tracking, ETA, or business logic
- Intelligence module contains documentation only
- No WebSocket, Redis, Kafka, or external service integrations

## Documentation

- [BUILD 0 Scope](docs/BUILD-0.md) — What BUILD 0 includes and excludes
- [Architecture Overview](docs/architecture.md) — System design and principles
- [Backend README](backend/README.md) — Backend-specific documentation
