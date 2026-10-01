# Dockerfile for FastAPI Backend

FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies needed for asyncpg/SQLAlchemy if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies file
# The pyproject.toml is available, let's use pip to install from it.
# We'll copy the pyproject.toml and the source directory so pip can install it.
COPY pyproject.toml .
# We need an empty README to satisfy build tools if specified
RUN touch README.md

# Install standard dependencies into user space
RUN pip install --user --no-cache-dir .

# -------------------------
# Final Stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy the application source code
COPY ./app ./app

# Ensure local bin is on PATH for uvicorn
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Switch to non-root user
USER appuser

EXPOSE 8009

# Start Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009", "--proxy-headers"]
