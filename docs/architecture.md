# Architecture Overview

## System Description

An intelligent public-transport platform for fragmented bus networks,
demonstrated through a small-city / tier-2/3 transport scenario.

## Core Architecture Principle

```
RAW OBSERVATIONS
    ↓
VALIDATION
    ↓
IMMUTABLE EVENTS
    ↓
INTELLIGENCE
    ↓
CANONICAL BUS STATE
    ↓
ETA PREDICTIONS
    ↓
PUBLIC STATE
    ↓
JOURNEY INTELLIGENCE
    ↓
PASSENGER DECISION
```

> Events are immutable observations.
> Bus State is the system's best available interpretation of those observations.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Android App | Kotlin, Jetpack Compose, Room |
| Backend API | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL, PostGIS |
| Admin Web | Vite, React, TypeScript |
| Realtime | WebSocket |
| Infrastructure | Docker Compose |
| Architecture | Modular monolith |

## Repository Structure

```
transit-platform/
├── apps/
│   ├── android/         # Android application (Passenger + Operator roles)
│   └── admin-web/       # Admin web application
├── backend/             # FastAPI modular monolith
├── shared/              # Shared contracts and documentation
├── infra/               # Infrastructure configuration
├── docs/                # Architecture and developer documentation
├── scripts/             # Development and utility scripts
├── docker-compose.yml   # Service definitions
└── README.md            # Developer documentation
```

## Backend Dependency Rule

```
API Layer
    ↓
Business Service
    ↓
Repository
    ↓
Database

Intelligence:
    Business Service → Intelligence Module → Repository
```

Intelligence modules must NOT depend on HTTP.
Business logic must NOT live in API routes.

## BUILD 0 Status

This document describes the target architecture.
Only the foundation infrastructure exists in BUILD 0.
Domain implementation begins in BUILD 1 after human approval.
