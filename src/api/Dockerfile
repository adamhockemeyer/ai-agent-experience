# Use Python 3.12 slim - good balance of security and compatibility
FROM python:3.12.8-slim-bookworm

WORKDIR /code

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Install system dependencies and Node.js with security updates
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && \
    # Install Node.js 20 LTS
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    # Install MCP GraphQL globally
    npm install -g --omit=dev mcp-graphql && \
    npm cache clean --force && \
    # Clean up to reduce attack surface
    apt-get purge -y --auto-remove curl gnupg && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Python requirements
COPY ./requirements.txt /code/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy application code and set ownership
COPY ./app /code/app
RUN chown -R appuser:appuser /code

# Switch to non-root user
USER appuser

EXPOSE 80

# Environment variables for optimal performance and security
ENV MCP_GRAPHQL_BIN=mcp-graphql
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONHASHSEED=random

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:80/health')" || exit 1

# Use uvicorn with production settings
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "1", "--log-level", "info"]