# Transit Platform — Backend

BUILD 0 foundation for the FastAPI modular-monolith backend.

## Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── api/routes/           # API route modules
│   ├── core/                 # Configuration, logging, security
│   ├── db/                   # Database engine, session management
│   ├── models/               # SQLAlchemy models (empty in BUILD 0)
│   ├── schemas/              # Pydantic schemas (empty in BUILD 0)
│   ├── repositories/         # Data access layer (empty in BUILD 0)
│   ├── services/             # Business logic (empty in BUILD 0)
│   └── intelligence/         # Intelligence modules (empty in BUILD 0)
├── tests/                    # Test suites
├── alembic/                  # Database migration framework
├── alembic.ini
└── pyproject.toml
```

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e ".[dev]"

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run linter
ruff check app/
```

## BUILD 0 Scope

This backend provides only:
- Health endpoints (`/health`, `/health/db`)
- Database connection infrastructure
- Alembic migration framework (no domain migrations)
- Logging foundation
- Environment-driven configuration

No domain models, business logic, or product APIs exist yet.
