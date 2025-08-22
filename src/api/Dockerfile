FROM python:3.12

WORKDIR /code

# Install Node.js (needed for MCP stdio tools like mcp-graphql) and globally install only the required package
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g --omit=dev mcp-graphql && \
    npm cache clean --force && \
    apt-get purge -y --auto-remove curl gnupg && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Python requirements
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

EXPOSE 80

# Environment hint so plugin config can switch from npx to direct binary if desired
ENV MCP_GRAPHQL_BIN=mcp-graphql

# Use uvicorn directly to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--log-level", "debug"]