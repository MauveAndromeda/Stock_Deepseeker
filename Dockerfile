# Stock Deepseeker - Quantitative Trading Research Platform
# Multi-stage build for optimized and secure container

# ============================================================================
# Stage 1: Builder - Compile dependencies
# ============================================================================
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    make \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy only dependency files first (for better caching)
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir -e ".[prod]"

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.10-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r deepseeker && \
    useradd -r -g deepseeker -u 1000 -m -s /bin/bash deepseeker

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Copy application code with correct ownership
COPY --chown=deepseeker:deepseeker . .

# Create necessary directories with correct ownership
RUN mkdir -p \
    data \
    logs \
    backtest_results \
    models \
    institutional_results \
    comparison_results \
    && chown -R deepseeker:deepseeker \
    data \
    logs \
    backtest_results \
    models \
    institutional_results \
    comparison_results

# Switch to non-root user
USER deepseeker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose API port
EXPOSE 8000

# Default command
CMD ["python", "-c", "print('Stock Deepseeker - Quantitative Trading Research Platform\\n\\nUsage:\\n  Quick backtest: python quick_backtest.py\\n  Advanced backtest: python advanced_backtest.py\\n  Institutional backtest: python institutional_backtest.py --start 2015-01-01\\n\\nFor more information, see README.md')"]

# ============================================================================
# Stage 3: Development - With dev tools
# ============================================================================
FROM runtime AS development

USER root

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    nano \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Install development dependencies
RUN pip install --no-cache-dir -e ".[dev,ai,rl,viz]"

# Install Jupyter
RUN pip install --no-cache-dir jupyter jupyterlab ipython

# Switch back to non-root user
USER deepseeker

# Expose Jupyter port
EXPOSE 8888

# Default command for development
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]

# ============================================================================
# Stage 4: Testing - For CI/CD
# ============================================================================
FROM development AS testing

USER root

# Install test dependencies
RUN pip install --no-cache-dir pytest pytest-cov pytest-xdist pytest-asyncio

# Copy test files
COPY --chown=deepseeker:deepseeker tests/ /app/tests/

USER deepseeker

# Run tests as default command
CMD ["pytest", "tests/", "-v", "--cov=src", "--cov-report=term-missing"]
