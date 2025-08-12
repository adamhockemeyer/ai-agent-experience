"""
Cosmos DB manager for vector storage and hybrid search.
Connects to pre-existing database and container configured via Bicep.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from models import DocumentChunk, DocumentMetadata, SearchRequest, SearchResult, SearchResponse, DocumentType, ProcessingStatus
from config import settings
from embedding_generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class CosmosDBManager:
    """Manages Cosmos DB operations for document storage and hybrid search."""
    
    def __init__(self):
        """Initialize Cosmos DB client and connect to existing database/container."""
        self.credential = DefaultAzureCredential()
        
        # Initialize embedding generator for query embeddings
        self.embedding_generator = EmbeddingGenerator()
        
        # Data plane client for data operations (uses managed identity)
        self.client = CosmosClient(
            url=settings.COSMOS_ENDPOINT,
            credential=self.credential
        )
        
        # Connect to existing database and container (created by Bicep)
        self.database = self.client.get_database_client(settings.COSMOS_DATABASE_NAME)
        self.container = self.database.get_container_client(settings.COSMOS_CONTAINER_NAME)
        
        logger.info(f"Connected to Cosmos DB: {settings.COSMOS_DATABASE_NAME}/{settings.COSMOS_CONTAINER_NAME}")
        
        # Verify connection by checking container properties
        try:
            container_properties = self.container.read()
            logger.info(f"Container properties loaded successfully. Partition key: {container_properties.get('partitionKey', 'Not found')}")
        except Exception as e:
            logger.error(f"Failed to connect to Cosmos DB container: {e}")
            raise
    
    def check_document_exists(self, document_id: str) -> bool:
        """Check if a document already exists in the database by looking for metadata."""
        try:
            metadata_id = f"metadata_{document_id}"
            self.container.read_item(
                item=metadata_id,
                partition_key=document_id
            )
            return True
        except CosmosResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking document existence: {e}")
            raise
    
    def store_document_chunks(self, chunks: List[DocumentChunk]) -> bool:
        """Store document chunks in Cosmos DB."""
        try:
            if not chunks:
                return True
            
            logger.info(f"Storing {len(chunks)} chunks in Cosmos DB")
            
            for chunk in chunks:
                item = {
                    "id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "content_length": chunk.content_length,
                    "token_count": chunk.token_count,
                    "embedding": chunk.embedding,
                    "blob_url": chunk.blob_url,
                    "blob_name": chunk.blob_name,
                    "document_type": chunk.document_type,
                    "file_extension": chunk.file_extension,
                    "processed_at": chunk.processed_at.isoformat(),
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char
                }
                
                # Upsert the chunk
                self.container.upsert_item(item)
            
            logger.info(f"Successfully stored {len(chunks)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Error storing chunks: {e}")
            raise
    
    def store_document_metadata(self, metadata: DocumentMetadata) -> bool:
        """Store document metadata in a separate partition."""
        try:
            # Store metadata with a different document type to separate from chunks
            item = {
                "id": f"metadata_{metadata.id}",
                "document_id": metadata.id,
                "blob_url": metadata.blob_url,
                "blob_name": metadata.blob_name,
                "container_name": metadata.container_name,
                "document_type": "METADATA",  # Special type for metadata
                "file_extension": metadata.file_extension,
                "file_size": metadata.file_size,
                "content_type": metadata.content_type,
                "last_modified": metadata.last_modified.isoformat(),
                "processed_at": metadata.processed_at.isoformat(),
                "processing_status": metadata.processing_status,
                "chunk_count": metadata.chunk_count,
                "error_message": metadata.error_message,
                "original_document_type": metadata.document_type
            }
            
            self.container.upsert_item(item)
            logger.info(f"Stored metadata for document {metadata.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing metadata: {e}")
            raise
    
    def _build_hybrid_search_query(self, request: SearchRequest) -> str:
        """Build hybrid search SQL query with vector and text search."""
        # Base SELECT clause
        select_fields = [
            "c.id as chunk_id",
            "c.document_id",
            "c.document_type",
            "c.blob_name",
            "c.blob_url",
            "c.chunk_index"
        ]
        
        if request.include_content:
            select_fields.append("c.content")
        
        # Add vector similarity score if embeddings are available
        if request.query_embedding and len(request.query_embedding) > 0:
            embedding_str = '[' + ', '.join(map(str, request.query_embedding)) + ']'
            select_fields.append(f"VectorDistance(c.embedding, {embedding_str}) AS vector_distance")
        
        # Build WHERE clause for document type filtering
        where_conditions = ["c.document_type != 'METADATA'"]  # Exclude metadata documents
        
        if request.document_types:
            doc_types = [f"'{dt}'" for dt in request.document_types]
            where_conditions.append(f"c.document_type IN ({', '.join(doc_types)})")
        
        where_clause = " AND ".join(where_conditions)
        
        # Build ORDER BY clause based on search type
        order_by_clauses = []
        
        # Vector search component
        if request.query_embedding and request.vector_weight > 0:
            order_by_clauses.append("VectorDistance(c.embedding, " + embedding_str + ")")
        
        # Text search component  
        if request.query_text and request.keyword_weight > 0:
            # Use proper Cosmos DB full-text search instead of basic CONTAINS
            # FullTextContainsAny works better for multi-word queries than CONTAINS
            query_words = request.query_text.split()
            if len(query_words) == 1:
                # Single word: use FullTextContains for exact phrase matching
                text_condition = f"FullTextContains(c.content, '{request.query_text}')"
            else:
                # Multi-word: use FullTextContainsAny for better recall
                # This finds documents containing ANY of the words
                word_list = ', '.join([f'"{word}"' for word in query_words])
                text_condition = f"FullTextContainsAny(c.content, {word_list})"
            where_conditions.append(text_condition)
            where_clause = " AND ".join(where_conditions)
        
        # Use vector distance for ordering if available, otherwise use chunk_index
        if order_by_clauses:
            order_by = f"ORDER BY {order_by_clauses[0]}"
        else:
            order_by = "ORDER BY c.chunk_index"
        
        # Construct final query
        query = f"""
        SELECT TOP {request.top_k} {', '.join(select_fields)}
        FROM c
        WHERE {where_clause}
        {order_by}
        """
        
        logger.info(f"Executing hybrid search query with vector={request.vector_weight}, keyword={request.keyword_weight}")
        logger.debug(f"Query: {query}")
        return query
    
    def _convert_to_search_results(self, items: List[Dict[str, Any]], include_content: bool, vector_weight: float = 0.6, keyword_weight: float = 0.4) -> List[SearchResult]:
        """Convert Cosmos DB query results to SearchResult objects with proper scoring."""
        results = []
        
        if not items:
            logger.info("No search results found")
            return results
        
        for item in items:
            try:
                # Calculate vector similarity score (distance to similarity conversion)
                vector_distance = item.get("vector_distance", 1.0)
                vector_score = max(0.0, 1.0 - vector_distance) if vector_distance is not None else 0.0
                
                # For keyword score, use a base score since we don't have full-text scoring yet
                # In a full implementation, this would come from Cosmos DB's full-text search score
                keyword_score = 0.8 if item.get("content") else 0.0
                
                # Calculate combined search score using weights
                search_score = (vector_score * vector_weight) + (keyword_score * keyword_weight)
                
                # Overall relevance score
                overall_score = search_score
                
                result = SearchResult(
                    chunk_id=item.get("chunk_id", ""),
                    document_id=item.get("document_id", ""),
                    score=overall_score,
                    search_score=search_score,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                    content=item.get("content") if include_content else None,
                    document_type=item.get("document_type", "GENERAL"),
                    blob_name=item.get("blob_name", ""),
                    blob_url=item.get("blob_url", ""),
                    chunk_index=item.get("chunk_index", 0)
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Error converting search result: {e}")
                continue
        
        # Sort results by overall score (descending)
        results.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"Converted {len(results)} search results with vector scoring")
        return results
    
    def vector_search(self, request: SearchRequest) -> SearchResponse:
        """Perform pure vector similarity search."""
        start_time = datetime.now()
        
        try:
            # Generate query embedding if not provided
            if not request.query_embedding and request.query_text:
                logger.info(f"Generating embedding for vector search: {request.query_text}")
                request.query_embedding = self.embedding_generator.generate_query_embedding(request.query_text)
                logger.info(f"Generated embedding with {len(request.query_embedding)} dimensions")
            
            if not request.query_embedding:
                logger.warning("No query embedding available for vector search")
                return SearchResponse(
                    results=[],
                    total_results=0,
                    query_text=request.query_text,
                    processing_time_ms=0
                )
            
            # Build vector-only search query
            query = self._build_vector_search_query(request)
            
            # Execute query
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True,
                max_item_count=request.top_k
            ))
            
            logger.info(f"Found {len(items)} items from vector search query")
            
            # Convert to search results (vector-only, so keyword_weight = 0)
            results = self._convert_to_search_results(items, request.include_content, vector_weight=1.0, keyword_weight=0.0)
            
            if results is None:
                results = []
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=results,
                total_results=len(results),
                query_text=request.query_text,
                processing_time_ms=int(processing_time)
            )
            
        except Exception as e:
            logger.error(f"Error performing vector search: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return SearchResponse(
                results=[],
                total_results=0,
                query_text=request.query_text,
                processing_time_ms=int(processing_time)
            )
    
    def _build_vector_search_query(self, request: SearchRequest) -> str:
        """Build vector-only search SQL query."""
        if not request.query_embedding:
            raise ValueError("Query embedding is required for vector search")
        
        embedding_str = '[' + ', '.join(map(str, request.query_embedding)) + ']'
        
        # Base SELECT clause
        select_fields = [
            "c.id as chunk_id",
            "c.document_id", 
            "c.document_type",
            "c.blob_name",
            "c.blob_url",
            "c.chunk_index",
            f"VectorDistance(c.embedding, {embedding_str}) AS vector_distance"
        ]
        
        if request.include_content:
            select_fields.append("c.content")
        
        # Build WHERE clause for document type filtering
        where_conditions = ["c.document_type != 'METADATA'"]  # Exclude metadata documents
        
        if request.document_types:
            doc_types = [f"'{dt}'" for dt in request.document_types]
            where_conditions.append(f"c.document_type IN ({', '.join(doc_types)})")
        
        where_clause = " AND ".join(where_conditions)
        
        # Order by vector similarity (ascending distance = highest similarity first)
        order_by = f"ORDER BY VectorDistance(c.embedding, {embedding_str})"
        
        # Construct final query
        query = f"""
        SELECT TOP {request.top_k} {', '.join(select_fields)}
        FROM c
        WHERE {where_clause}
        {order_by}
        """
        
        logger.info(f"Executing vector search query")
        logger.debug(f"Query: {query}")
        return query
    
    def keyword_search(self, request: SearchRequest) -> SearchResponse:
        """Perform pure keyword search without vector components."""
        start_time = datetime.now()
        
        try:
            if not request.query_text:
                logger.warning("No query text provided for keyword search")
                return SearchResponse(
                    results=[],
                    total_results=0,
                    query_text=request.query_text or "",
                    processing_time_ms=0
                )
            
            # Build keyword-only search query
            query = self._build_keyword_search_query(request)
            
            # Execute query
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True,
                max_item_count=request.top_k
            ))
            
            logger.info(f"Found {len(items)} items from keyword search query")
            
            # Convert to search results (keyword-only, so vector_weight = 0)
            results = self._convert_to_search_results(items, request.include_content, vector_weight=0.0, keyword_weight=1.0)
            
            if results is None:
                results = []
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=results,
                total_results=len(results),
                query_text=request.query_text,
                processing_time_ms=int(processing_time)
            )
            
        except Exception as e:
            logger.error(f"Error performing keyword search: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return SearchResponse(
                results=[],
                total_results=0,
                query_text=request.query_text or "",
                processing_time_ms=int(processing_time)
            )
    
    def _build_keyword_search_query(self, request: SearchRequest) -> str:
        """Build keyword-only search SQL query."""
        if not request.query_text:
            raise ValueError("Query text is required for keyword search")
        
        # Base SELECT clause
        select_fields = [
            "c.id as chunk_id",
            "c.document_id", 
            "c.document_type",
            "c.blob_name",
            "c.blob_url",
            "c.chunk_index"
        ]
        
        if request.include_content:
            select_fields.append("c.content")
        
        # Build WHERE clause for document type filtering
        where_conditions = ["c.document_type != 'METADATA'"]  # Exclude metadata documents
        
        if request.document_types:
            doc_types = [f"'{dt}'" for dt in request.document_types]
            where_conditions.append(f"c.document_type IN ({', '.join(doc_types)})")
        
        # Add text search conditions using proper full-text search
        query_words = request.query_text.split()
        if len(query_words) == 1:
            # Single word: use FullTextContains for exact matching
            text_condition = f"FullTextContains(c.content, '{request.query_text}')"
        else:
            # Multi-word: use FullTextContainsAny for better recall
            word_list = ', '.join([f'"{word}"' for word in query_words])
            text_condition = f"FullTextContainsAny(c.content, {word_list})"
        where_conditions.append(text_condition)
        
        where_clause = " AND ".join(where_conditions)
        
        # Order by chunk_index for keyword search
        order_by = "ORDER BY c.chunk_index"
        
        # Construct final query
        query = f"""
        SELECT TOP {request.top_k} {', '.join(select_fields)}
        FROM c
        WHERE {where_clause}
        {order_by}
        """
        
        logger.info(f"Executing keyword search query")
        logger.debug(f"Query: {query}")
        return query
    
    def hybrid_search(self, request: SearchRequest) -> SearchResponse:
        """Perform hybrid search using Cosmos DB's RRF (Reciprocal Rank Fusion)."""
        start_time = datetime.now()
        
        try:
            # Generate query embedding if not provided
            if not request.query_embedding and request.query_text:
                logger.info(f"Generating embedding for RRF hybrid search: {request.query_text}")
                request.query_embedding = self.embedding_generator.generate_query_embedding(request.query_text)
                logger.info(f"Generated embedding with {len(request.query_embedding)} dimensions")
            
            if not request.query_embedding or not request.query_text:
                logger.warning("Both query embedding and text are required for RRF hybrid search")
                return SearchResponse(
                    results=[],
                    total_results=0,
                    query_text=request.query_text or "",
                    processing_time_ms=0
                )
            
            # Build RRF hybrid search query
            query = self._build_rrf_hybrid_query(request)
            
            # Execute query
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True,
                max_item_count=request.top_k
            ))
            
            logger.info(f"Found {len(items)} items from RRF hybrid search query")
            
            # Convert to search results with RRF scoring
            results = self._convert_rrf_results(items, request.include_content)
            
            if results is None:
                results = []
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=results,
                total_results=len(results),
                query_text=request.query_text,
                processing_time_ms=int(processing_time)
            )
            
        except Exception as e:
            logger.error(f"Error performing RRF hybrid search: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return SearchResponse(
                results=[],
                total_results=0,
                query_text=request.query_text or "",
                processing_time_ms=int(processing_time)
            )
    
    def _build_rrf_hybrid_query(self, request: SearchRequest) -> str:
        """Build RRF hybrid search query using VectorDistance and FullTextScore."""
        if not request.query_embedding or not request.query_text:
            raise ValueError("Both query embedding and text are required for RRF hybrid search")
        
        embedding_str = '[' + ', '.join(map(str, request.query_embedding)) + ']'
        
        # Build query words for full-text search - each word as separate string argument
        query_words = request.query_text.split()
        # FullTextScore requires separate string arguments, not an array
        word_args = ', '.join([f'"{word}"' for word in query_words])
        
        # Base SELECT clause
        select_fields = [
            "c.id as chunk_id",
            "c.document_id", 
            "c.document_type",
            "c.blob_name",
            "c.blob_url",
            "c.chunk_index"
        ]
        
        if request.include_content:
            select_fields.append("c.content")
        
        # Build WHERE clause for document type filtering
        where_conditions = ["c.document_type != 'METADATA'"]
        
        if request.document_types:
            doc_types = [f"'{dt}'" for dt in request.document_types]
            where_conditions.append(f"c.document_type IN ({', '.join(doc_types)})")
        
        where_clause = " AND ".join(where_conditions)
        
        # Use RRF with VectorDistance and FullTextScore - each word as separate string argument
        rrf_clause = f"RRF(FullTextScore(c.content, {word_args}), VectorDistance(c.embedding, {embedding_str}))"
        
        # Construct final query with ORDER BY RANK RRF
        query = f"""
        SELECT TOP {request.top_k} {', '.join(select_fields)}
        FROM c
        WHERE {where_clause}
        ORDER BY RANK {rrf_clause}
        """
        
        logger.info(f"Executing RRF hybrid search query with corrected FullTextScore syntax")
        logger.debug(f"Query: {query}")
        return query
    
    def _convert_rrf_results(self, items: List[Dict[str, Any]], include_content: bool) -> List[SearchResult]:
        """Convert RRF query results to SearchResult objects."""
        results = []
        
        if not items:
            logger.info("No RRF search results found")
            return results
        
        for i, item in enumerate(items):
            try:
                # RRF provides built-in ranking, so use position as score
                rrf_score = 1.0 / (i + 1)  # Higher rank = higher score
                
                result = SearchResult(
                    chunk_id=item.get("chunk_id", ""),
                    document_id=item.get("document_id", ""),
                    score=rrf_score,
                    search_score=rrf_score,  # RRF combined score
                    vector_score=rrf_score,  # Part of RRF
                    keyword_score=rrf_score,  # Part of RRF  
                    content=item.get("content") if include_content else None,
                    document_type=item.get("document_type", "GENERAL"),
                    blob_name=item.get("blob_name", ""),
                    blob_url=item.get("blob_url", ""),
                    chunk_index=item.get("chunk_index", 0)
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Error converting RRF search result: {e}")
                continue
        
        logger.info(f"Converted {len(results)} RRF search results")
        return results
    
    def get_document_chunks(self, document_id: str) -> List[DocumentChunk]:
        """Get all chunks for a specific document."""
        try:
            # More efficient query since all chunks are in the same partition
            query = "SELECT * FROM c WHERE c.document_id = @document_id AND c.id != @metadata_id"
            parameters = [
                {"name": "@document_id", "value": document_id},
                {"name": "@metadata_id", "value": f"metadata_{document_id}"}
            ]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=document_id  # More efficient - single partition query
            ))
            
            chunks = []
            for item in items:
                chunk = DocumentChunk(
                    id=item["id"],
                    document_id=item["document_id"],
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    content_length=item["content_length"],
                    token_count=item["token_count"],
                    embedding=item["embedding"],
                    blob_url=item["blob_url"],
                    blob_name=item["blob_name"],
                    document_type=item["document_type"],
                    file_extension=item["file_extension"],
                    processed_at=datetime.fromisoformat(item["processed_at"]),
                    start_char=item.get("start_char"),
                    end_char=item.get("end_char")
                )
                chunks.append(chunk)
            
            return sorted(chunks, key=lambda x: x.chunk_index)
            
        except Exception as e:
            logger.error(f"Error getting document chunks: {e}")
            raise

    def get_document_metadata(self, document_id: str) -> Optional[DocumentMetadata]:
        """Get metadata for a specific document."""
        try:
            # Direct read using point operation - most efficient
            metadata_id = f"metadata_{document_id}"
            item = self.container.read_item(
                item=metadata_id,
                partition_key=document_id
            )
            
            return DocumentMetadata(
                id=item["document_id"],  # Use document_id as the main id
                blob_url=item["blob_url"],
                blob_name=item["blob_name"],
                container_name=item.get("container_name", "documents"),
                document_type=item.get("original_document_type", item.get("document_type", "ROOT")),
                file_extension=item["file_extension"],
                file_size=item["file_size"],
                content_type=item.get("content_type", "application/octet-stream"),
                last_modified=datetime.fromisoformat(item["last_modified"]) if item.get("last_modified") else datetime.utcnow(),
                processed_at=datetime.fromisoformat(item["processed_at"]) if item.get("processed_at") else datetime.utcnow(),
                processing_status=ProcessingStatus(item["processing_status"]),
                chunk_count=item.get("chunk_count", 0),
                error_message=item.get("error_message")
            )
            
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting document metadata: {e}")
            raise

    def list_documents(self, document_type: Optional[str] = None, limit: int = 100) -> List[DocumentMetadata]:
        """List document metadata with optional filtering by type."""
        try:
            # Query for metadata documents only
            if document_type:
                query = "SELECT * FROM c WHERE STARTSWITH(c.id, 'metadata_') AND c.original_document_type = @doc_type ORDER BY c.processed_at DESC OFFSET 0 LIMIT @limit"
                parameters = [
                    {"name": "@doc_type", "value": document_type},
                    {"name": "@limit", "value": limit}
                ]
            else:
                query = "SELECT * FROM c WHERE STARTSWITH(c.id, 'metadata_') ORDER BY c.processed_at DESC OFFSET 0 LIMIT @limit"
                parameters = [{"name": "@limit", "value": limit}]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            documents = []
            for item in items:
                metadata = DocumentMetadata(
                    id=item["document_id"],  # Use document_id as the main id
                    blob_url=item["blob_url"],
                    blob_name=item["blob_name"],
                    container_name=item.get("container_name", "documents"),
                    document_type=item.get("original_document_type", item.get("document_type", "ROOT")),
                    file_extension=item["file_extension"],
                    file_size=item["file_size"],
                    content_type=item.get("content_type", "application/octet-stream"),
                    last_modified=datetime.fromisoformat(item["last_modified"]) if item.get("last_modified") else datetime.utcnow(),
                    processed_at=datetime.fromisoformat(item["processed_at"]) if item.get("processed_at") else datetime.utcnow(),
                    processing_status=ProcessingStatus(item["processing_status"]),
                    chunk_count=item.get("chunk_count", 0),
                    error_message=item.get("error_message")
                )
                documents.append(metadata)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            raise

    def get_available_document_types(self) -> List[str]:
        """Get all available document types from the database."""
        try:
            query = """
            SELECT DISTINCT c.original_document_type as document_type
            FROM c 
            WHERE STARTSWITH(c.id, 'metadata_') AND c.original_document_type != null
            ORDER BY c.original_document_type
            """
            
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            document_types = [item["document_type"] for item in items if item.get("document_type")]
            return sorted(document_types)
            
        except Exception as e:
            logger.error(f"Error getting document types: {e}")
            raise
    
    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks and metadata for a document."""
        try:
            # Get all items for this document (chunks + metadata)
            query = "SELECT c.id FROM c WHERE c.document_id = @document_id"
            parameters = [{"name": "@document_id", "value": document_id}]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            # Delete all items - they all have the same partition key (document_id)
            for item in items:
                self.container.delete_item(
                    item=item["id"],
                    partition_key=document_id
                )
            
            logger.info(f"Deleted {len(items)} items for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise
