# Use official Python 3.12 slim image for a lightweight, secure container
FROM python:3.12-slim

# Prevent Python from writing pyc files to disc (equivalent to python -B)
ENV PYTHONDONTWRITEBYTECODE=1

# Prevent Python from buffering stdout and stderr (equivalent to python -u)
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

# Set working directory
WORKDIR /app

# Install OS-level dependencies (if any are needed for PostGIS/ psycopg2 etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first to cache dependencies
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir ".[dev]"

# Copy application code
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose port
EXPOSE 8000

# Start Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
