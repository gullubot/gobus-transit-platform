# Infrastructure

Docker, database, and development infrastructure configuration.

## Contents

- `../docker-compose.yml` — Service definitions (PostgreSQL/PostGIS)
- Future: additional infrastructure scripts and configurations

## BUILD 0

Infrastructure in BUILD 0 consists of:
- Docker Compose with PostgreSQL 16 + PostGIS 3.4
- Environment-driven configuration via `.env`

No additional infrastructure services (Redis, Kafka, monitoring) are
included per the locked specification.
