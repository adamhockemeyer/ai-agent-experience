# Document Processing and Search Azure Functions

A comprehensive Azure Functions app that processes documents using **MarkItDown**, generates embeddings, stores them in **Cosmos DB with vector search**, and provides **MCP (Model Context Protocol) tools** for hybrid search functionality.

## 🌟 Features

### Document Processing
- **Event Grid Blob Trigger**: Automatically processes new/modified documents in blob storage
- **MarkItDown Integration**: Converts 20+ file formats (PDF, DOCX, PPTX, images, etc.) to markdown
- **Intelligent Chunking**: Uses LangChain text splitters with configurable chunk size and overlap
- **Azure Document Intelligence**: Optional integration for enhanced document parsing
- **LLM Image Descriptions**: Optional LLM integration for image content descriptions

### Vector Search & Storage
- **Cosmos DB NoSQL**: Vector storage with hybrid search capabilities
- **Azure OpenAI Embeddings**: Generates high-quality embeddings using text-embedding-ada-002
- **Hybrid Search**: Combines vector similarity and full-text search using RRF (Reciprocal Rank Fusion)
- **Document Type Classification**: Automatic classification based on folder structure

### MCP Tools
- **Native MCP Support**: Exposes search functionality as MCP tools
- **Multiple Search Modes**: Hybrid, semantic (vector-only), and keyword (full-text) search
- **Rich Metadata**: Includes document types, blob URLs, processing timestamps

### Utility Features
- **Manual Processing**: HTTP endpoint for processing existing documents
- **Batch Operations**: Process multiple documents with job tracking
- **Statistics & Monitoring**: Index statistics and document counts
- **Error Handling**: Comprehensive error handling with retry logic

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Blob Storage  │───▶│  Azure Function │───▶│   Cosmos DB     │
│   (Documents)   │    │  (Processing)   │    │ (Vector Store)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   MarkItDown    │
                       │  + Azure OpenAI │
                       │   (Embeddings)  │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   MCP Tools     │
                       │ (Search & AI)   │
                       └─────────────────┘
```

## 📁 Project Structure

```
├── function_app.py          # Main Azure Functions app (document processing)
├── mcp_tools.py            # MCP tools for search functionality
├── models.py               # Pydantic data models
├── config.py               # Configuration settings
├── document_processor.py   # MarkItDown document processing
├── embedding_generator.py  # Azure OpenAI embedding generation
├── cosmos_manager.py       # Cosmos DB operations
├── mcp_tools.py           # MCP tools for search
├── utility.py             # Setup and testing utilities
├── requirements.txt       # Python dependencies
└── local.settings.template.json  # Configuration template
```

## 🚀 Quick Start

### 1. Prerequisites

- Azure subscription with the following resources:
  - Azure Storage Account (with blob storage)
  - Azure Cosmos DB for NoSQL (with vector search enabled)
  - Azure OpenAI Service (with text-embedding-ada-002 deployment)
  - Optional: Azure Document Intelligence
- Azure Functions Core Tools
- Python 3.9+

### 2. Setup

1. **Clone and navigate to the project**:
   ```bash
   cd src/api-mcp-search-index
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure settings**:
   ```bash
   cp local.settings.template.json local.settings.json
   # Edit local.settings.json with your Azure resource endpoints
   ```

4. **Enable Cosmos DB vector search**:
   ```bash
   az cosmosdb update \
     --resource-group <resource-group> \
     --name <cosmos-account> \
     --capabilities EnableNoSQLVectorSearch
   ```

5. **Set up the database and test the system**:
   ```bash
   python utility.py setup
   python utility.py test-full
   ```

### 3. Deploy to Azure

```bash
func azure functionapp publish <your-function-app-name>
```

## 📋 Configuration

### Required Settings

| Setting | Description |
|---------|-------------|
| `AzureWebJobsStorage` | Azure Storage connection string |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint URL |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI service endpoint |

### Optional Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `AZURE_DOC_INTELLIGENCE_ENDPOINT` | Document Intelligence endpoint | None |
| `LLM_CLIENT_ENDPOINT` | LLM endpoint for image descriptions | None |
| `LLM_MODEL` | LLM model for image descriptions | gpt-4o |
| `CHUNK_SIZE` | Text chunk size in characters | 1000 |
| `CHUNK_OVERLAP` | Overlap between chunks | 200 |
| `EMBEDDING_DIMENSIONS` | Embedding vector dimensions | 1536 |
| `MAX_FILE_SIZE_MB` | Maximum file size for processing | 100 |

## 📄 Document Types

Documents are automatically classified based on folder structure:

- `documents/SDS/` → SDS (Safety Data Sheets)
- `documents/MANUAL/` → MANUAL (User Manuals)  
- `documents/LABEL/` → LABEL (Product Labels)
- `documents/` (root) → GENERAL (General Documents)

## 🔍 MCP Tools

### Available Tools

1. **hybrid_search**: Combines vector similarity and keyword search
2. **semantic_search**: Pure vector similarity search
3. **keyword_search**: Full-text keyword search only
4. **get_document_info**: Get index statistics and document counts

### Usage Example

```json
{
  "method": "tools/call",
  "params": {
    "name": "hybrid_search",
    "arguments": {
      "query": "safety procedures for chemicals",
      "document_types": ["SDS", "MANUAL"],
      "top_k": 10,
      "include_content": true,
      "vector_weight": 1.0,
      "text_weight": 1.0
    }
  }
}
```

## 🛠️ Utility Commands

```bash
# Set up Cosmos DB
python utility.py setup

# Test components
python utility.py test-connection
python utility.py test-embedding
python utility.py test-processing
python utility.py test-full

# Get index statistics
python utility.py stats

# Clear all documents
python utility.py clear
```

## 🔄 Processing Workflow

1. **Document Upload**: Files uploaded to `documents/` container in blob storage
2. **Event Trigger**: Event Grid triggers the Azure Function
3. **Format Detection**: Check file type and size limits
4. **Document Conversion**: MarkItDown converts to markdown
5. **Text Chunking**: Split into overlapping chunks
6. **Embedding Generation**: Create vector embeddings using Azure OpenAI
7. **Storage**: Store chunks and metadata in Cosmos DB
8. **Search Ready**: Documents available for hybrid search

## 🔧 API Endpoints

### Manual Processing
`POST /api/process-documents`

Process existing documents or reindex:

```json
{
  "container_name": "documents",
  "blob_prefix": "SDS/",
  "force_reprocess": false,
  "document_types": ["SDS"]
}
```

### MCP Search Server  
`POST /api/mcp/search`

MCP protocol endpoint for search tools.

## 🏷️ Supported File Formats

MarkItDown supports:
- **Documents**: PDF, DOCX, DOC, PPTX, PPT, RTF, ODT
- **Spreadsheets**: XLSX, XLS, CSV
- **Text**: TXT, MD, HTML
- **Images**: PNG, JPG, JPEG, BMP, TIFF, GIF (with optional LLM descriptions)

## 🔐 Security & Authentication

- **Managed Identity**: Uses Azure Managed Identity for secure, credential-free authentication
- **RBAC**: Follows Azure RBAC best practices
- **No Hardcoded Secrets**: All credentials managed through Azure services

## 📊 Monitoring & Logging

- **Application Insights**: Integrated logging and monitoring
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Error Tracking**: Comprehensive error handling and reporting
- **Performance Metrics**: Processing times and throughput tracking

## 🛡️ Error Handling

- **Retry Logic**: Exponential backoff for transient failures
- **Graceful Degradation**: Continue processing other documents if one fails
- **Error Storage**: Failed documents logged with error details
- **Circuit Breaker**: Prevents cascade failures

## 🤝 Contributing

1. Follow Azure best practices for serverless applications
2. Use Pydantic models for data validation
3. Include comprehensive error handling
4. Add tests for new functionality
5. Update documentation

## 📝 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

1. **Cosmos DB Vector Search Not Enabled**
   ```bash
   az cosmosdb update --resource-group <rg> --name <account> --capabilities EnableNoSQLVectorSearch
   ```

2. **Embedding Dimension Mismatch**
   - Check `EMBEDDING_DIMENSIONS` setting matches your model
   - text-embedding-ada-002 uses 1536 dimensions

3. **File Processing Failures**
   - Check file size limits (`MAX_FILE_SIZE_MB`)
   - Verify supported file extensions
   - Review Document Intelligence configuration

4. **MCP Tool Errors**
   - Ensure Cosmos DB container has proper vector policies
   - Check embedding generation is working
   - Verify search query syntax

### Getting Help

- Check Azure Function logs in Application Insights
- Use `python utility.py test-full` to verify system health
- Review Cosmos DB query metrics
- Check Azure OpenAI service quotas and usage
