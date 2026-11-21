# OLIGOBOT V10 - Dockerfile
# Multi-stage build for smaller final image

# ==========================================
# Stage 1: Build dependencies
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==========================================
# Stage 2: Runtime image
# ==========================================
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd -r oligobot && useradd -r -g oligobot -d /app -s /sbin/nologin oligobot

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Create directories for runtime data
RUN mkdir -p /app/brain_index /app/chroma_clinical_v2 /app/eadl_index /app/logs \
    && chown -R oligobot:oligobot /app

# Switch to non-root user
USER oligobot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port (for admin dashboard)
EXPOSE 8080

# Default command
CMD ["python", "app.py"]
