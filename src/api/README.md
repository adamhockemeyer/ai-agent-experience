# Backend API

This is a Python FastAPI application that serves as the backend for the AI Agents demo environment. It provides chat API endpoints that interact with Azure OpenAI services and leverages Semantic Kernel to create dynamic agents based on configuration stored in Azure App Configuration.

## Environment Variables

The following environment variables are required to run the backend API:

| Variable Name | Description | Required |
|---------------|-------------|----------|
| `AZURE_OPENAI_API_KEY` | API key for Azure OpenAI service | No* |
| `AZURE_OPENAI_ENDPOINT` | Endpoint URL for Azure OpenAI service | Yes |
| `AZURE_AI_API_KEY` | API key for Azure AI service | No* |
| `AZURE_AI_ENDPOINT` | Endpoint URL for Azure AI service | Yes |
| `AZURE_APP_CONFIG_ENDPOINT` | Endpoint URL for Azure App Configuration | Yes** |
| `AZURE_APP_CONFIG_CONNECTION_STRING` | Connection string for Azure App Configuration | No*** |
| `AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING` | Connection string for Azure Application Insights telemetry | No |
| `THREAD_STORAGE_TYPE` | Storage type for conversation threads: "memory" or "cosmosdb" | No (defaults to "memory") |
| `COSMOS_DB_ENDPOINT` | Endpoint for CosmosDB | Only if THREAD_STORAGE_TYPE="cosmosdb" |
| `COSMOS_DB_CONNECTION_STRING` | Connection string for CosmosDB | No**** |
| `COSMOS_DB_DATABASE_NAME` | Database name in CosmosDB | No (defaults to "aiagents-db") |
| `COSMOS_DB_CONTAINER_NAME` | Container name in CosmosDB | No (defaults to "chatHistory") |
| `COSMOS_DB_PARTITION_KEY` | Partition Key in CosmosDB | No (defaults to "partitionKey") |
| `MCP_ENABLE_PLUGINS` | Enable Model Context Protocol plugins | No (defaults to true) |
| `SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE` | Enable OpenTelemetry diagnostics for GenAI content | No (defaults to false) |

\* If API key is not provided, DefaultAzureCredential will be used for authentication.  
\** Either `AZURE_APP_CONFIG_ENDPOINT` or `AZURE_APP_CONFIG_CONNECTION_STRING` must be provided.  
\*** Required only if `AZURE_APP_CONFIG_ENDPOINT` is not set.  
\**** If not provided, DefaultAzureCredential will be used with the endpoint for authentication.

## Running the Application

### Local Development

1. Create and activate a virtual environment:
   ```
   cd src/api
   python -m venv .venv
   
   # On Windows
   .venv\Scripts\activate
   
   # On Linux/Mac
   source .venv/bin/activate
   ```

2. Create a `.env` file in the `src/api` directory with the required environment variables.

3. Install dependencies:
   ```
   pip install -r requirements.txt
   pip install -r dev-requirements.txt  # For development tools
   ```

4. Start the development server:
   ```
   uvicorn app.main:app --reload --env-file .env
   ```

5. Access the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs)

### Docker Container

The application can be run as a Docker container:

```
docker build -t ai-agents-api -f src/api/Dockerfile .
docker run -p 80:80 \
  -e AZURE_OPENAI_ENDPOINT=your-endpoint \
  -e AZURE_AI_ENDPOINT=your-endpoint \
  -e AZURE_APP_CONFIG_ENDPOINT=your-endpoint \
  ai-agents-api
```

## API Endpoints

The main API endpoints include:

- `POST /api/chat` - Send a message to a chat agent

For complete API documentation, check the Swagger UI at `/docs` when the server is running.