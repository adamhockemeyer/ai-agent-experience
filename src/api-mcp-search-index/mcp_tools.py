"""
MCP (Model Context Protocol) tools for document search functionality.
Extracted from function_app.py for better organization.

PERFORMANCE MONITORING:
- Comprehensive timing instrumentation added to identify bottlenecks
- Tracks operation timing: CosmosDB init, context parsing, database calls, result formatting
- First query cold start performance (target: identify 6000ms → 2000ms improvements)
- Logs timing for: hybrid_search, semantic_search, keyword_search, get_document_info, get_document_types
- TimingContext manager for detailed operation breakdown
- Overall function timing with detailed sub-operation logging
"""
import azure.functions as func
import logging
import json
import time
import warnings
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse
from functools import lru_cache

from models import SearchRequest, DocumentType
from cosmos_manager import CosmosDBManager
from config import settings
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

def log_timing(operation_name: str, start_time: float, details: str = "") -> float:
    """Log timing information for operations."""
    duration_ms = (time.time() - start_time) * 1000
    details_str = f" - {details}" if details else ""
    logger.info(f"⏱️ MCP Timing: {operation_name} took {duration_ms:.2f}ms{details_str}")
    return duration_ms

class TimingContext:
    """Context manager for timing operations."""
    def __init__(self, operation_name: str, details: str = ""):
        self.operation_name = operation_name
        self.details = details
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"🚀 MCP Starting: {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            log_timing(self.operation_name, self.start_time, self.details)

def generate_blob_sas_url_fast(blob_url: str, cached_sas_token: str = None) -> str:
    """
    Ultra-fast SAS URL generation using pre-computed token.
    Use this when you have a cached container-level SAS token.
    
    Args:
        blob_url: The original blob URL
        cached_sas_token: Pre-computed SAS token for the container
        
    Returns:
        The blob URL with SAS token appended
    """
    try:
        if not blob_url:
            return blob_url
            
        if cached_sas_token:
            separator = '&' if '?' in blob_url else '?'
            return f"{blob_url}{separator}{cached_sas_token}"
        else:
            # Fallback to regular generation
            return generate_blob_sas_url(blob_url)
            
    except Exception as e:
        logger.error(f"Error generating fast SAS token for {blob_url}: {e}")
        return blob_url

def generate_blob_sas_url(blob_url: str) -> str:
    """
    Generate a SAS token for a blob URL to provide secure access.
    OPTIMIZED: Uses cached blob clients and user delegation keys.
    
    Args:
        blob_url: The original blob URL
        
    Returns:
        The blob URL with SAS token appended
    """
    try:
        if not blob_url:
            return blob_url
            
        # Parse the blob URL to extract components
        parsed_url = urlparse(blob_url)
        storage_account_name = parsed_url.netloc.split('.')[0]
        
        # Extract container and blob name from path
        path_parts = parsed_url.path.strip('/').split('/', 1)
        if len(path_parts) < 2:
            logger.warning(f"Invalid blob URL format: {blob_url}")
            return blob_url
            
        container_name = path_parts[0]
        blob_name = path_parts[1]
        
        # Use cached blob service client
        blob_service_client = get_cached_blob_client(storage_account_name)
        
        # Use cached user delegation key
        user_delegation_key = get_cached_user_delegation_key(blob_service_client, storage_account_name)
        
        # Generate SAS token with read permissions valid for 24 hours
        sas_token = generate_blob_sas(
            account_name=storage_account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=None,
            user_delegation_key=user_delegation_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=24)
        )
        
        # Append SAS token to URL
        separator = '&' if parsed_url.query else '?'
        return f"{blob_url}{separator}{sas_token}"
        
    except Exception as e:
        logger.error(f"Error generating SAS token for {blob_url}: {e}")
        # Return original URL if SAS generation fails
        return blob_url

# Initialize Cosmos manager with timing
cosmos_manager_init_start = time.time()
logger.info("🚀 Initializing CosmosDBManager...")
cosmos_manager = CosmosDBManager()
cosmos_manager_init_duration = log_timing("CosmosDBManager initialization", cosmos_manager_init_start)

# Global cache for SAS token optimization
_blob_service_clients: Dict[str, BlobServiceClient] = {}
_user_delegation_keys: Dict[str, Tuple[object, datetime]] = {}  # (key, expiry_time)

def get_cached_blob_client(storage_account_name: str) -> BlobServiceClient:
    """Get or create cached blob service client."""
    if storage_account_name not in _blob_service_clients:
        storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
        _blob_service_clients[storage_account_name] = BlobServiceClient(
            account_url=storage_account_url,
            credential=DefaultAzureCredential()
        )
    return _blob_service_clients[storage_account_name]

def get_cached_user_delegation_key(blob_service_client: BlobServiceClient, storage_account_name: str):
    """Get or create cached user delegation key."""
    now = datetime.utcnow()
    
    # Check if we have a valid cached key
    if storage_account_name in _user_delegation_keys:
        key, expiry = _user_delegation_keys[storage_account_name]
        if now < expiry - timedelta(hours=1):  # Refresh 1 hour before expiry
            return key
    
    # Create new delegation key
    key_start_time = now
    key_expiry_time = now + timedelta(hours=23)  # 23 hours to be safe
    
    user_delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time=key_start_time,
        key_expiry_time=key_expiry_time
    )
    
    _user_delegation_keys[storage_account_name] = (user_delegation_key, key_expiry_time)
    return user_delegation_key


class ToolProperty:
    """Helper class for defining MCP tool properties in the correct Azure Functions format."""
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description
        }


# Define tool properties using the correct Azure Functions MCP format
# For MCP tools with Semantic Kernel, we expose only the most useful parameters
# with very specific guidance to ensure LLMs provide appropriate values

hybrid_search_properties = [
    ToolProperty("query", "string", "Search query text (REQUIRED)"),
    ToolProperty("top_k", "integer", "Number of results to return. Use 5 for quick results, 10 for standard results, or 20 for comprehensive results. Default: 10"),
    ToolProperty("document_types", "string", "Filter documents by type. Use empty string '' to search all documents, or specify document types as comma-separated values (e.g., 'TYPE1,TYPE2'). Call get_document_types tool first to see available document types. Default: search all documents")
]

semantic_search_properties = [
    ToolProperty("query", "string", "Search query text (REQUIRED)"),
    ToolProperty("top_k", "integer", "Number of results to return. Use 5 for quick results, 10 for standard results, or 20 for comprehensive results. Default: 10"),
    ToolProperty("document_types", "string", "Filter documents by type. Use empty string '' to search all documents, or specify document types as comma-separated values (e.g., 'TYPE1,TYPE2'). Call get_document_types tool first to see available document types. Default: search all documents")
]

keyword_search_properties = [
    ToolProperty("query", "string", "Search query text (REQUIRED)"),
    ToolProperty("top_k", "integer", "Number of results to return. Use 5 for quick results, 10 for standard results, or 20 for comprehensive results. Default: 10"),
    ToolProperty("document_types", "string", "Filter documents by type. Use empty string '' to search all documents, or specify document types as comma-separated values (e.g., 'TYPE1,TYPE2'). Call get_document_types tool first to see available document types. Default: search all documents")
]

document_info_properties = []

list_documents_properties = []

get_document_types_properties = []

# Convert to JSON format for Azure Functions
HYBRID_SEARCH_PROPERTIES = json.dumps([prop.to_dict() for prop in hybrid_search_properties])
SEMANTIC_SEARCH_PROPERTIES = json.dumps([prop.to_dict() for prop in semantic_search_properties])
KEYWORD_SEARCH_PROPERTIES = json.dumps([prop.to_dict() for prop in keyword_search_properties])
DOCUMENT_INFO_PROPERTIES = json.dumps([prop.to_dict() for prop in document_info_properties])
LIST_DOCUMENTS_PROPERTIES = json.dumps([prop.to_dict() for prop in list_documents_properties])
GET_DOCUMENT_TYPES_PROPERTIES = json.dumps([prop.to_dict() for prop in get_document_types_properties])


def register_mcp_tools(app: func.FunctionApp):
    """Register all MCP tools with the Azure Functions app."""
    

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger", 
        toolName="semantic_search",
        description="Perform semantic search across documents using vector similarity for conceptual matching. BEST FOR: 'how to' questions, procedural queries, conceptual relationships, troubleshooting guidance. Parameters: query (required), top_k (5/10/20 for quick/standard/comprehensive results), document_types ('' for all documents, or use get_document_types tool to see available types for filtering). PERFORMANCE: <6000ms first query, <2000ms subsequent.",
        toolProperties=SEMANTIC_SEARCH_PROPERTIES
    )
    def semantic_search_mcp(context) -> str:
        """
        MCP tool for semantic/vector search.
        
        Args:
            context: MCP tool context containing the arguments
            
        Returns:
            str: Formatted search results
        """
        overall_start = time.time()
        logger.info(f"🚀 MCP semantic_search_mcp started")
        
        try:
            with TimingContext("Parse MCP context and arguments"):
                # Parse context and arguments
                content = json.loads(context)
                arguments = content.get("arguments", {})
                
                query = arguments.get("query", "")
                if not query.strip():
                    log_timing("TOTAL semantic_search_mcp (empty query)", overall_start)
                    return "❌ Query cannot be empty."
                
                # Create search request (vector only)
                document_types_param = arguments.get("document_types")
                document_types_list = None
                if document_types_param and document_types_param.strip():
                    # Split comma-separated string into list
                    document_types_list = [dt.strip() for dt in document_types_param.split(",") if dt.strip()]
                
                top_k = min(arguments.get("top_k", 10), 50)
                include_content = arguments.get("include_content", True)
                
                logger.info(f"Semantic search: query='{query[:50]}...', top_k={top_k}, types={document_types_param}")
            
            with TimingContext("Create SearchRequest object"):
                search_request = SearchRequest(
                    query_text=query,
                    top_k=top_k,
                    document_types=document_types_list,
                    include_content=include_content,
                    vector_weight=1.0,  # Vector only
                    keyword_weight=0.0
                )
            
            with TimingContext("Perform vector search", f"query: {query[:30]}..."):
                # Perform search using vector search method
                response = cosmos_manager.vector_search(search_request)
            
            with TimingContext("Format search results"):
                # Format response
                lines = [
                    f"🎯 **Semantic Search Results**",
                    f"Query: \"{response.query_text}\"", 
                    f"Found {response.total_results} results in {response.processing_time_ms}ms",
                    ""
                ]
                
                if not response.results:
                    lines.append("No results found.")
                else:
                    for i, result in enumerate(response.results, 1):
                        lines.extend([
                            f"**{i}. {result.blob_name}** (Similarity: {result.vector_score:.3f})",
                            f"   • Type: {result.document_type} | Chunk {result.chunk_index}",
                            f"   • Download: {generate_blob_sas_url(result.blob_url)}",
                            f"   • Preview: {result.content[:200]}..." if result.content and len(result.content) > 200 else f"   • Content: {result.content}" if result.content else "   • Content: [Content not included]",
                            ""
                        ])
            
            total_duration = log_timing("TOTAL semantic_search_mcp", overall_start, f"found {len(response.results)} results")
            return "\n".join(lines)
            
        except Exception as e:
            total_duration = log_timing("TOTAL semantic_search_mcp (ERROR)", overall_start, str(e))
            logger.error(f"Error in semantic_search_mcp: {e}")
            return f"❌ Error performing semantic search: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="keyword_search", 
        description="Perform fast keyword search across documents using full-text search with BM25 scoring for exact term matching. BEST FOR: exact terms, product names, technical specifications, ID numbers, specific phrases, regulatory data (LD50, EPA numbers). Parameters: query (required), top_k (5/10/20 for quick/standard/comprehensive results), document_types ('' for all documents, or use get_document_types tool to see available types for filtering). PERFORMANCE: <1000ms response time.",
        toolProperties=KEYWORD_SEARCH_PROPERTIES
    )
    def keyword_search_mcp(context) -> str:
        """
        MCP tool for keyword/full-text search.
        
        Args:
            context: MCP tool context containing the arguments
            
        Returns:
            str: Formatted search results
        """
        overall_start = time.time()
        logger.info(f"🚀 MCP keyword_search_mcp started")
        
        try:
            with TimingContext("Parse MCP context and arguments"):
                # Parse context and arguments
                content = json.loads(context)
                arguments = content.get("arguments", {})
                
                query = arguments.get("query", "")
                if not query.strip():
                    log_timing("TOTAL keyword_search_mcp (empty query)", overall_start)
                    return "❌ Query cannot be empty."
                
                # Create search request (keyword only)
                document_types_param = arguments.get("document_types")
                document_types_list = None
                if document_types_param and document_types_param.strip():
                    # Split comma-separated string into list
                    document_types_list = [dt.strip() for dt in document_types_param.split(",") if dt.strip()]
                
                top_k = min(arguments.get("top_k", 10), 50)
                include_content = arguments.get("include_content", True)
                
                logger.info(f"Keyword search: query='{query[:50]}...', top_k={top_k}, types={document_types_param}")
            
            with TimingContext("Create SearchRequest object"):
                search_request = SearchRequest(
                    query_text=query,
                    top_k=top_k,
                    document_types=document_types_list,
                    include_content=include_content,
                    vector_weight=0.0,  # Keyword only
                    keyword_weight=1.0
                )
            
            with TimingContext("Perform keyword search", f"query: {query[:30]}..."):
                # Perform search using dedicated keyword search method
                response = cosmos_manager.keyword_search(search_request)
            
            with TimingContext("Format search results"):
                # Format response
                lines = [
                    f"🔎 **Keyword Search Results**",
                    f"Query: \"{response.query_text}\"",
                    f"Found {response.total_results} results in {response.processing_time_ms}ms",
                    ""
                ]
                
                if not response.results:
                    lines.append("No results found.")
                else:
                    for i, result in enumerate(response.results, 1):
                        lines.extend([
                            f"**{i}. {result.blob_name}** (Score: {result.keyword_score:.3f})",
                            f"   • Type: {result.document_type} | Chunk {result.chunk_index}",
                            f"   • Download: {generate_blob_sas_url(result.blob_url)}",
                            f"   • Preview: {result.content[:200]}..." if result.content and len(result.content) > 200 else f"   • Content: {result.content}" if result.content else "   • Content: [Content not included]",
                            ""
                        ])
            
            total_duration = log_timing("TOTAL keyword_search_mcp", overall_start, f"found {len(response.results)} results")
            return "\n".join(lines)
            
        except Exception as e:
            total_duration = log_timing("TOTAL keyword_search_mcp (ERROR)", overall_start, str(e))
            logger.error(f"Error in keyword_search_mcp: {e}")
            return f"❌ Error performing keyword search: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="get_document_info",
        description="Get detailed information about document types, counts, or specific document details. Use for document inventory, processing status verification, or when user asks about specific documents. Provides comprehensive metadata including chunk counts, processing status, and file details. Optional parameter: document_id (if not provided, returns general statistics).",
        toolProperties=DOCUMENT_INFO_PROPERTIES
    )
    def get_document_info_mcp(context) -> str:
        """
        MCP tool to get document information.
        
        Args:
            context: MCP tool context containing the arguments
            
        Returns:
            str: Formatted document information
        """
        overall_start = time.time()
        logger.info(f"🚀 MCP get_document_info_mcp started")
        
        try:
            with TimingContext("Parse MCP context and arguments"):
                # Parse context and arguments
                content = json.loads(context)
                arguments = content.get("arguments", {})
                document_id = arguments.get("document_id")
                
                logger.info(f"Document info request: document_id={document_id}")
            
            # If document_id provided, get specific document info
            if document_id:
                with TimingContext("Get specific document info", f"doc_id: {document_id}"):
                    # Normalize document ID format (replace '/' with '_' for consistency)
                    document_id = document_id.replace('/', '_')
                    metadata = cosmos_manager.get_document_metadata(document_id)
                    if not metadata:
                        log_timing("TOTAL get_document_info_mcp (not found)", overall_start)
                        return f"❌ Document with ID '{document_id}' not found."
                    
                    chunks = cosmos_manager.get_document_chunks(document_id)
                
                # Format response
                response = f"""📄 **Document Information**

**Basic Details:**
• **File Name:** {metadata.blob_name}
• **Document ID:** {metadata.id}
• **Type:** {metadata.document_type}
• **File Extension:** {metadata.file_extension}
• **File Size:** {metadata.file_size:,} bytes
• **Processing Status:** {metadata.processing_status}

**Processing Details:**
• **Total Chunks:** {metadata.chunk_count}
• **Processed At:** {metadata.processed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if metadata.processed_at else 'Not processed'}

**Storage Details:**
• **Blob URL:** {generate_blob_sas_url(metadata.blob_url)}
• **Blob Name:** {metadata.blob_name}"""

                if metadata.error_message:
                    response += f"\n• **Error:** {metadata.error_message}"

                if chunks:
                    response += f"\n\n**Chunk Details:**"
                    for chunk in chunks[:5]:  # Show first 5 chunks
                        response += f"\n• **Chunk {chunk.chunk_index}:** {chunk.content_length} chars, {chunk.token_count} tokens"
                    
                    if len(chunks) > 5:
                        response += f"\n• *... and {len(chunks) - 5} more chunks*"
                
                return response
            
            # Otherwise, return general statistics
            # Get total chunks count
            total_chunks_query = """
            SELECT VALUE COUNT(1)
            FROM c 
            WHERE NOT STARTSWITH(c.id, 'metadata_')
            """
            
            total_chunks_items = list(cosmos_manager.container.query_items(
                query=total_chunks_query,
                enable_cross_partition_query=True
            ))
            
            total_chunks = total_chunks_items[0] if total_chunks_items else 0
            
            # Get document count
            doc_count_query = """
            SELECT VALUE COUNT(1)
            FROM c 
            WHERE STARTSWITH(c.id, 'metadata_')
            """
            
            doc_count_items = list(cosmos_manager.container.query_items(
                query=doc_count_query,
                enable_cross_partition_query=True
            ))
            
            total_documents = doc_count_items[0] if doc_count_items else 0
            
            # Get document types for display
            types_query = """
            SELECT DISTINCT VALUE c.document_type
            FROM c 
            WHERE NOT STARTSWITH(c.id, 'metadata_')
            """
            
            type_items = list(cosmos_manager.container.query_items(
                query=types_query,
                enable_cross_partition_query=True
            ))
            
            # Format statistics
            info_lines = ["📊 **Document Index Statistics**", ""]
            
            info_lines.extend([
                f"**Total**: {total_documents} documents, {total_chunks} chunks",
                "",
                "🔍 **Available Search Types**:",
                "- `hybrid_search`: Combines vector similarity and keyword matching",
                "- `semantic_search`: Vector similarity search only",  
                "- `keyword_search`: Full-text keyword search only",
                "",
                f"📁 **Document Types Available**: {', '.join(type_items) if type_items else 'None'}"
            ])
            
            return "\n".join(info_lines)
            
        except Exception as e:
            logger.error(f"Error in get_document_info_mcp: {e}")
            return f"❌ Error retrieving document information: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_documents",
        description="List recent documents with optional filtering by document type. Use when user needs document inventory ('what documents are available'), processing status verification, or document metadata overview. Shows document processing status, chunk counts, and file information. Optional parameters: document_type (filter by type), limit=20 (max 100). NOTE: For general inventory questions ('what's available'), first call get_document_types to see all types, then optionally call this tool without document_type filter or try get_document_info without document_id.",
        toolProperties=LIST_DOCUMENTS_PROPERTIES
    )
    def list_documents_mcp(context) -> str:
        """
        MCP tool to list documents.
        
        Args:
            context: MCP tool context containing the arguments
            
        Returns:
            str: Formatted list of documents
        """
        try:
            # Parse context and arguments
            content = json.loads(context)
            arguments = content.get("arguments", {})
            document_type_str = arguments.get("document_type")
            limit = min(arguments.get("limit", 20), 100)
            
            # Convert string to enum if provided
            document_type = None
            if document_type_str:
                # No need to validate since we're using dynamic strings now
                document_type = document_type_str
            
            # Get documents from Cosmos
            documents = cosmos_manager.list_documents(document_type=document_type, limit=limit)
            
            if not documents:
                type_filter = f" of type {document_type_str}" if document_type_str else ""
                return f"📄 No documents found{type_filter}."
            
            # Format response
            type_filter = f" ({document_type_str})" if document_type_str else ""
            response_lines = [
                f"📄 **Recent Documents{type_filter}**",
                f"Showing {len(documents)} document(s):",
                ""
            ]
            
            for doc in documents:
                status_icon = "✅" if doc.processing_status == "COMPLETED" else "⏳" if doc.processing_status == "PROCESSING" else "❌"
                processed_date = doc.processed_at.strftime('%Y-%m-%d %H:%M') if doc.processed_at else "Not processed"
                
                response_lines.extend([
                    f"{status_icon} **{doc.blob_name}**",
                    f"   • **ID:** `{doc.id}`",
                    f"   • **Type:** {doc.document_type}",
                    f"   • **Size:** {doc.file_size:,} bytes",
                    f"   • **Status:** {doc.processing_status}",
                    f"   • **Processed:** {processed_date}",
                    f"   • **Chunks:** {doc.chunk_count}",
                    ""
                ])
            
            return "\n".join(response_lines)
            
        except Exception as e:
            logger.error(f"Error in list_documents_mcp: {e}")
            return f"❌ Error listing documents: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="get_document_types",
        description="Get all available document types in the database. USE ONLY when you need to filter searches to specific document types. For general queries, use search tools WITHOUT document_types parameter to search across ALL documents. This tool helps when users specifically mention document categories (labels, manuals, safety data sheets, etc.).",
        toolProperties=GET_DOCUMENT_TYPES_PROPERTIES
    )
    def get_document_types_mcp(context) -> str:
        """
        MCP tool to get available document types.
        
        Args:
            context: MCP tool context (no arguments needed)
            
        Returns:
            str: Formatted list of available document types
        """
        overall_start = time.time()
        logger.info(f"🚀 MCP get_document_types_mcp started")
        
        try:
            with TimingContext("Get available document types from Cosmos"):
                # Get available document types from Cosmos
                document_types = cosmos_manager.get_available_document_types()
            
            with TimingContext("Format document types response"):
                if not document_types:
                    log_timing("TOTAL get_document_types_mcp (no types)", overall_start)
                    return "📁 No document types found. Upload some documents first."
                
                # Format response
                response_lines = [
                    "📁 **Available Document Types**",
                    f"Found {len(document_types)} document type(s):",
                    ""
                ]
                
                for doc_type in document_types:
                    if doc_type == "ROOT":
                        response_lines.append(f"• **{doc_type}** - Files in container root (no folder)")
                    else:
                        response_lines.append(f"• **{doc_type}** - Files in '{doc_type.lower()}/' folder")
            
            total_duration = log_timing("TOTAL get_document_types_mcp", overall_start, f"found {len(document_types)} types")
            
            response_lines.extend([
                "",
                "💡 **Usage Tips:**",
                "- **DEFAULT**: Leave document_types empty to search ALL documents (most efficient)",
                "- **FILTER ONLY**: Use document_types only when user specifically mentions document categories",
                "- **FORMAT**: Use comma-separated values like 'LABELS,MANUALS' or single type 'SDS'",
                "- **AVOID**: Don't make multiple search calls with different document types - use one search across all types instead",
                "- Document types are automatically determined from folder structure",
                "- Files in the root container get type 'ROOT'",
                "- Folder names are converted to uppercase for consistency"
            ])
            
            return "\n".join(response_lines)
            
        except Exception as e:
            logger.error(f"Error in get_document_types_mcp: {e}")
            return f"❌ Error retrieving document types: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="hybrid_search",
        description="Perform hybrid search across documents using Reciprocal Rank Fusion (RRF) combining vector similarity with keyword matching for optimal ranking. BEST FOR: Most complex queries, mixed conceptual/technical questions, comprehensive research needs. RECOMMENDED DEFAULT for general queries. Parameters: query (required), top_k (5/10/20 for quick/standard/comprehensive results), document_types ('' for all documents, or use get_document_types tool to see available types for filtering). PERFORMANCE: <3500ms with superior result quality.",
        toolProperties=HYBRID_SEARCH_PROPERTIES
    )
    def hybrid_search_mcp(context) -> str:
        """
        MCP tool for hybrid search combining vector and full-text search using RRF.

        Args:
            context: MCP tool context containing the arguments

        Returns:
            str: Formatted search results with RRF ranking
        """
        overall_start = time.time()
        logger.info(f"🚀 MCP hybrid_search_mcp started")
        
        try:
            with TimingContext("Parse MCP context and arguments"):
                # Parse context and arguments
                content = json.loads(context)
                arguments = content.get("arguments", {})
                
                query = arguments.get("query", "")
                if not query.strip():
                    log_timing("TOTAL hybrid_search_mcp (empty query)", overall_start)
                    return "❌ Query cannot be empty."
                
                top_k = min(arguments.get("top_k", 10), 50)
                document_types = arguments.get("document_types", "")
                include_content = arguments.get("include_content", True)  # Changed default to True
                vector_weight = arguments.get("vector_weight", 0.6)
                keyword_weight = arguments.get("keyword_weight", 0.4)
                
                logger.info(f"Hybrid search: query='{query[:50]}...', top_k={top_k}, types={document_types}")
            
            with TimingContext("Normalize weights and prepare doc types"):
                # Normalize weights
                total_weight = vector_weight + keyword_weight
                if total_weight > 0:
                    vector_weight = vector_weight / total_weight
                    keyword_weight = keyword_weight / total_weight
                else:
                    vector_weight = 0.6
                    keyword_weight = 0.4
                
                # Convert document_types string to list
                doc_types_list = []
                if document_types:
                    doc_types_list = [dt.strip() for dt in document_types.split(",") if dt.strip()]
            
            with TimingContext("Create SearchRequest object"):
                # Create SearchRequest object for RRF hybrid search
                from models import SearchRequest
                search_request = SearchRequest(
                    query_text=query,
                    query_embedding=None,  # Will be generated by the method
                    top_k=top_k,
                    document_types=doc_types_list,
                    include_content=include_content,
                    vector_weight=vector_weight,
                    keyword_weight=keyword_weight
                )
            
            with TimingContext("Perform RRF hybrid search", f"query: {query[:30]}..."):
                # Perform RRF hybrid search
                search_response = cosmos_manager.hybrid_search(search_request)
                results = search_response.results
            
            with TimingContext("Process and format results"):
                if not results:
                    doc_filter = f" in document types: {document_types}" if document_types else ""
                    total_duration = log_timing("TOTAL hybrid_search_mcp (no results)", overall_start)
                    return f"🔍 No results found for query: '{query}'{doc_filter}.\n\nTry:\n• Different search terms\n• Broader document type filters\n• Checking document types with get_document_types"
                
                with TimingContext("Format basic response structure"):
                    # Format results
                    doc_filter = f" ({document_types})" if document_types else ""
                    response_lines = [
                        f"🔍 **RRF Hybrid Search Results{doc_filter}**",
                        f"Query: *{query}*",
                        f"Found {len(results)} result(s) using RRF ranking (vector: {vector_weight:.1f}, keyword: {keyword_weight:.1f}):",
                        ""
                    ]
                
                sas_generation_start = time.time()
                with TimingContext("Generate all SAS tokens", f"for {len(results)} results"):
                    for i, result in enumerate(results, 1):
                        # Access SearchResult attributes directly (not as dictionary)
                        rrf_score = result.search_score
                        vector_score = result.vector_score
                        keyword_score = result.keyword_score
                        
                        # Generate SAS URL (this is the bottleneck!)
                        sas_url = generate_blob_sas_url(result.blob_url)
                        
                        response_lines.extend([
                            f"**{i}. {result.blob_name}** (Type: {result.document_type})",
                            f"   📊 **RRF Score:** {rrf_score:.4f} (Vector: {vector_score:.3f}, Keyword: {keyword_score:.3f})",
                            f"   📄 **Chunk:** {result.chunk_index}",
                            f"   📖 **Source:** `{result.chunk_id}`",
                            f"   📥 **Download:** {sas_url}"
                        ])
                        
                        if include_content and result.content:
                            content_preview = result.content
                            if len(content_preview) > 300:
                                content_preview = content_preview[:297] + "..."
                            response_lines.extend([
                                f"   📝 **Content Preview:** {content_preview}",
                                ""
                            ])
                        else:
                            response_lines.append("")
                
                log_timing("SAS token generation for all results", sas_generation_start, f"{len(results)} tokens")
            
            total_duration = log_timing("TOTAL hybrid_search_mcp", overall_start, f"found {len(results)} results")
            
            response_lines.extend([
                "💡 **About RRF Search:**",
                "• Combines vector similarity and full-text BM25 scoring",
                "• Uses Reciprocal Rank Fusion for optimal ranking",
                "• Vector search finds semantically similar content", 
                "• Full-text search matches keywords with BM25 scoring",
                "• RRF merges rankings to surface the most relevant results"
            ])
            
            return "\n".join(response_lines)
            
        except Exception as e:
            logger.error(f"Error in hybrid_search_rrf_mcp: {e}")
            return f"❌ Error performing RRF hybrid search: {str(e)}"
