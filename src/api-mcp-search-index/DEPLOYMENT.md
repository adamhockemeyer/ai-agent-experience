# Deployment Guide

## Prerequisites

Before deploying the Azure Functions app, ensure you have the following Azure resources:

### Required Azure Resources

1. **Azure Storage Account**
   - General Purpose v2 storage account
   - Container named `documents` (or configured container name)
   - Event Grid subscription configured for blob events

2. **Azure Cosmos DB for NoSQL Account**
   - Enable vector search capability:
     ```bash
     az cosmosdb update \
       --resource-group <resource-group> \
       --name <cosmos-account> \
       --capabilities EnableNoSQLVectorSearch
     ```

3. **Azure OpenAI Service**
   - Deploy `text-embedding-ada-002` model
   - Note the endpoint and deployment name

4. **Optional: Azure Document Intelligence**
   - Deploy Document Intelligence service for enhanced parsing

5. **Azure Functions App**
   - Python 3.9+ runtime
   - Consumption or Premium plan

### Required RBAC Permissions

Assign the following roles to the Function App's Managed Identity:

1. **Storage Account**:
   - `Storage Blob Data Reader`
   - `Storage Queue Data Reader` (for Event Grid)

2. **Cosmos DB Account**:
   - `Cosmos DB Built-in Data Contributor`

3. **Azure OpenAI Service**:
   - `Cognitive Services OpenAI User`

4. **Optional - Document Intelligence**:
   - `Cognitive Services User`

## Deployment Steps

### 1. Deploy Infrastructure

You can use the provided Bicep templates in the `infra/` directory or create resources manually.

### 2. Configure Application Settings

Set the following application settings in your Function App:

```bash
# Required settings
az functionapp config appsettings set -g <resource-group> -n <function-app> --settings \
  COSMOS_ENDPOINT="https://<cosmos-account>.documents.azure.com:443/" \
  AZURE_OPENAI_ENDPOINT="https://<openai-service>.openai.azure.com/" \
  DOCUMENTS_CONTAINER_NAME="documents"

# Optional settings
az functionapp config appsettings set -g <resource-group> -n <function-app> --settings \
  AZURE_DOC_INTELLIGENCE_ENDPOINT="https://<doc-intel>.cognitiveservices.azure.com/" \
  LLM_CLIENT_ENDPOINT="https://<openai-service>.openai.azure.com/" \
  LLM_MODEL="gpt-4o"
```

### 3. Deploy Function Code

Using Azure Functions Core Tools:

```bash
# Build and deploy
func azure functionapp publish <function-app-name>
```

Using Azure CLI:

```bash
# Create deployment package
zip -r deployment.zip . -x ".venv/*" ".git/*" "*.pyc" "__pycache__/*"

# Deploy
az functionapp deployment source config-zip \
  -g <resource-group> \
  -n <function-app> \
  --src deployment.zip
```

### 4. Configure Event Grid

Set up Event Grid subscription for blob storage events:

```bash
# Get Function App's Event Grid trigger URL
FUNCTION_URL=$(az functionapp function show \
  -g <resource-group> \
  -n <function-app> \
  --function-name event_grid_blob_trigger \
  --query invokeUrlTemplate -o tsv)

# Create Event Grid subscription
az eventgrid event-subscription create \
  --name document-processing \
  --source-resource-id /subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account> \
  --endpoint $FUNCTION_URL \
  --endpoint-type webhook \
  --included-event-types Microsoft.Storage.BlobCreated Microsoft.Storage.BlobDeleted
```

### 5. Test the Deployment

1. **Test the setup utility**:
   ```bash
   # Run from local development environment
   python utility.py setup
   python utility.py test-full
   ```

2. **Upload a test document** to your storage container

3. **Check Application Insights** for processing logs

4. **Verify data in Cosmos DB** using Azure Portal

## Configuration Reference

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `AzureWebJobsStorage` | ✅ | Storage connection string | Connection string |
| `COSMOS_ENDPOINT` | ✅ | Cosmos DB endpoint | `https://mydb.documents.azure.com:443/` |
| `AZURE_OPENAI_ENDPOINT` | ✅ | Azure OpenAI endpoint | `https://myopenai.openai.azure.com/` |
| `DOCUMENTS_CONTAINER_NAME` | ❌ | Blob container name | `documents` |
| `AZURE_DOC_INTELLIGENCE_ENDPOINT` | ❌ | Document Intelligence endpoint | `https://mydocai.cognitiveservices.azure.com/` |
| `LLM_CLIENT_ENDPOINT` | ❌ | LLM endpoint for images | `https://myopenai.openai.azure.com/` |
| `LLM_MODEL` | ❌ | LLM model name | `gpt-4o` |
| `CHUNK_SIZE` | ❌ | Text chunk size | `1000` |
| `CHUNK_OVERLAP` | ❌ | Chunk overlap | `200` |
| `EMBEDDING_DIMENSIONS` | ❌ | Embedding dimensions | `1536` |
| `MAX_FILE_SIZE_MB` | ❌ | Max file size | `100` |

## Monitoring and Troubleshooting

### Application Insights

The function app automatically logs to Application Insights. Key metrics to monitor:

- **Function execution count and duration**
- **Error rates and exceptions**
- **Cosmos DB operation latency**
- **OpenAI API call success rates**

### Common Issues

1. **"Vector search not enabled"**
   - Ensure Cosmos DB has vector search capability enabled
   - Allow 15 minutes for the capability to take effect

2. **"Embedding dimension mismatch"**
   - Verify `EMBEDDING_DIMENSIONS` matches your model (1536 for ada-002)

3. **"Authentication failed"**
   - Check Managed Identity assignments
   - Verify RBAC permissions on resources

4. **"File processing timeout"**
   - Check file size limits
   - Consider using Premium plan for larger files
   - Verify Document Intelligence quota

### Scaling Considerations

- **Consumption Plan**: Good for light workloads, automatic scaling
- **Premium Plan**: Better for consistent workloads, faster cold starts
- **Cosmos DB**: Configure appropriate RU/s for your workload
- **OpenAI**: Monitor rate limits and quotas

## Security Best Practices

1. **Use Managed Identity** for all Azure service authentication
2. **Restrict network access** using VNets and private endpoints
3. **Enable diagnostic logging** for audit trails
4. **Use Key Vault** for any additional secrets
5. **Regular security updates** for dependencies

## Backup and Disaster Recovery

1. **Cosmos DB**: Enable automatic backups and configure backup policy
2. **Storage Account**: Enable soft delete and versioning
3. **Function App**: Use deployment slots for zero-downtime updates
4. **Infrastructure**: Maintain Infrastructure as Code templates

## MCP Integration Setup

### Get MCP Extension System Key

After deployment, get the MCP extension system key:

```bash
# Get the system key for MCP extension
az functionapp keys list \
  --resource-group <resource-group> \
  --name <function-app-name> \
  --query "systemKeys.mcp_extension" \
  --output tsv
```

### Configure MCP Clients

#### VS Code with GitHub Copilot

1. Create or update `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "document-search": {
      "type": "sse",
      "url": "https://<function-app-name>.azurewebsites.net/runtime/webhooks/mcp/sse",
      "headers": {
        "x-functions-key": "<mcp-extension-system-key>"
      }
    }
  }
}
```

2. Open Command Palette and run "MCP: List Servers"
3. Start the "document-search" server
4. Test by asking Copilot to search your documents

#### MCP Inspector

1. Install MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
```

2. Use the URL with key parameter:
```
https://<function-app-name>.azurewebsites.net/runtime/webhooks/mcp/sse?code=<mcp-extension-system-key>
```

### Available MCP Tools

The deployment provides these MCP tools:

- `hybrid_search`: Combines vector and keyword search
- `semantic_search`: Pure vector similarity search  
- `keyword_search`: Full-text keyword search
- `get_document_info`: Document statistics and specific document details
- `list_documents`: Browse recent documents with filtering

### Local Development MCP Testing

For local testing, use:
```
http://localhost:7071/runtime/webhooks/mcp/sse
```

No authentication required for local development.
