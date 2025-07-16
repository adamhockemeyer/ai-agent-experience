FROM python:3.12

WORKDIR /code

# Start - Playwright dependencies for demo purposes (local playwright MCP server)
# Install Node.js and npm
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Install Playwright and browsers
RUN npm init -y \
    && npm install playwright \
    && npx playwright install --with-deps --only-shell chrome

# End - Playwright dependencies for demo purposes (local playwright MCP server)

# Install Python requirements
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

EXPOSE 80

# Use uvicorn directly to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--log-level", "debug"]