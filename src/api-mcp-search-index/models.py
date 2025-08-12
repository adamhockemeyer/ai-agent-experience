"""
Pydantic models for document processing and storage.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class DocumentType(str, Enum):
    """Document types based on folder structure - dynamically determined."""
    # Default fallback for files not in folders
    ROOT = "ROOT"
    
    @classmethod
    def from_blob_path(cls, blob_path: str) -> str:
        """
        Determine document type from blob path.
        
        Args:
            blob_path: The blob path (e.g., "sds/document.pdf" or "document.pdf")
            
        Returns:
            str: Document type (folder name or "ROOT" if no folder)
        """
        if '/' in blob_path:
            # Extract first folder name and convert to uppercase
            folder = blob_path.split('/')[0].upper()
            return folder
        else:
            # File is in root of container
            return cls.ROOT.value
    
    @classmethod
    def create_dynamic_enum(cls, document_types: List[str]) -> 'DocumentType':
        """
        Create dynamic enum with discovered document types.
        
        Args:
            document_types: List of discovered document type strings
            
        Returns:
            Updated DocumentType enum class
        """
        # Create new enum members dynamically
        for doc_type in document_types:
            if not hasattr(cls, doc_type):
                setattr(cls, doc_type, doc_type)


class ProcessingStatus(str, Enum):
    """Processing status for documents."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """Metadata for processed documents."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    id: str = Field(..., description="Unique document identifier")
    blob_url: str = Field(..., description="Azure Blob Storage URL")
    blob_name: str = Field(..., description="Blob name/path")
    container_name: str = Field(..., description="Container name")
    document_type: str = Field(default="ROOT", description="Document type based on folder structure")
    file_extension: str = Field(..., description="File extension")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    last_modified: datetime = Field(..., description="Last modified timestamp")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, description="Processing status")
    chunk_count: int = Field(default=0, description="Number of chunks created")
    error_message: Optional[str] = Field(default=None, description="Error message if processing failed")


class DocumentChunk(BaseModel):
    """Individual document chunk for vector storage."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    chunk_index: int = Field(..., description="Chunk sequence number")
    content: str = Field(..., description="Chunk text content")
    content_length: int = Field(..., description="Content length in characters")
    token_count: int = Field(..., description="Estimated token count")
    embedding: List[float] = Field(..., description="Vector embedding")
    
    # Metadata inherited from parent document
    blob_url: str = Field(..., description="Source blob URL")
    blob_name: str = Field(..., description="Source blob name")
    document_type: str = Field(..., description="Document type")
    file_extension: str = Field(..., description="File extension")
    processed_at: datetime = Field(..., description="Processing timestamp")
    
    # Chunk-specific metadata
    start_char: Optional[int] = Field(default=None, description="Start character position in original document")
    end_char: Optional[int] = Field(default=None, description="End character position in original document")


class SearchRequest(BaseModel):
    """Request model for hybrid search."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    query_text: str = Field(..., description="Search query text")
    query_embedding: Optional[List[float]] = Field(default=None, description="Query vector embedding")
    document_types: Optional[List[str]] = Field(default=None, description="Filter by document types")
    top_k: int = Field(default=10, le=100, description="Number of results to return")
    include_content: bool = Field(default=True, description="Include chunk content in results")
    vector_weight: float = Field(default=1.0, ge=0.0, le=10.0, description="Weight for vector search component")
    keyword_weight: float = Field(default=1.0, ge=0.0, le=10.0, description="Weight for keyword search component")


class SearchResult(BaseModel):
    """Search result model."""
    model_config = ConfigDict()
    
    chunk_id: str = Field(..., description="Chunk identifier")
    document_id: str = Field(..., description="Document identifier")
    score: float = Field(default=0.0, description="Relevance score")
    search_score: float = Field(default=0.0, description="Combined search score for hybrid search")
    vector_score: float = Field(default=0.0, description="Vector similarity score")
    keyword_score: float = Field(default=0.0, description="Keyword/full-text search score")
    content: Optional[str] = Field(default=None, description="Chunk content")
    document_type: str = Field(..., description="Document type")
    blob_name: str = Field(..., description="Source blob name")
    blob_url: str = Field(..., description="Source blob URL")
    chunk_index: int = Field(..., description="Chunk sequence number")


class SearchResponse(BaseModel):
    """Response model for search results."""
    model_config = ConfigDict()
    
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results")
    query_text: str = Field(..., description="Original query text")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class ProcessingJobRequest(BaseModel):
    """Request model for manual processing jobs."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    container_name: str = Field(default="documents", description="Container to process")
    blob_prefix: Optional[str] = Field(default=None, description="Blob prefix filter")
    force_reprocess: bool = Field(default=False, description="Force reprocessing of existing documents")
    document_types: Optional[List[str]] = Field(default=None, description="Filter by document types")


class ProcessingJobStatus(BaseModel):
    """Status model for processing jobs."""
    model_config = ConfigDict()
    
    job_id: str = Field(..., description="Job identifier")
    status: ProcessingStatus = Field(..., description="Job status")
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion time")
    documents_processed: int = Field(default=0, description="Number of documents processed")
    documents_failed: int = Field(default=0, description="Number of failed documents")
    error_message: Optional[str] = Field(default=None, description="Error message if job failed")
