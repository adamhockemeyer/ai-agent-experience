"""
Azure Functions app for document processing.
MCP tools are now organized in mcp_tools.py for better project structure.
"""
import azure.functions as func
import logging
import json
import uuid
from datetime import datetime
from typing import List, Optional
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

from models import DocumentMetadata, ProcessingStatus, ProcessingJobRequest, ProcessingJobStatus
from document_processor import DocumentProcessor
from embedding_generator import EmbeddingGenerator
from cosmos_manager import CosmosDBManager
from config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Initialize Azure Functions app
app = func.FunctionApp()

# Initialize service instances
document_processor = DocumentProcessor()
embedding_generator = EmbeddingGenerator()
cosmos_manager = CosmosDBManager()

# Register MCP tools from separate module
from mcp_tools import register_mcp_tools
register_mcp_tools(app)

# Add a simple test MCP tool to verify setup



def get_blob_service_client() -> BlobServiceClient:
    """
    Get BlobServiceClient using DefaultAzureCredential for secure authentication.
    Falls back to connection string if needed for local development.
    """
    try:
        # Try DefaultAzureCredential first (recommended for production)
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(
            account_url=settings.DOCUMENTS_STORAGE_ACCOUNT_URL,
            credential=credential
        )
        # Test the connection
        blob_service_client.get_account_information()
        return blob_service_client
    except Exception as e:
        logger.warning(f"DefaultAzureCredential failed: {e}. Falling back to connection string.")
        # Fallback to connection string for local development
        if settings.DOCUMENTS_STORAGE_CONNECTION_STRING:
            return BlobServiceClient.from_connection_string(settings.DOCUMENTS_STORAGE_CONNECTION_STRING)
        else:
            logger.error("No fallback connection string available. Ensure managed identity is properly configured or provide a connection string.")
            raise


@app.event_grid_trigger(arg_name="eventGridEvent")
def event_grid_blob_trigger(eventGridEvent: func.EventGridEvent):
    """
    Event Grid trigger for processing blob changes.
    Triggered when files are added, modified, or deleted in the documents container.
    """
    try:
        # Parse Event Grid event data
        event_data = eventGridEvent.get_json()
        event_type = eventGridEvent.event_type
        subject = eventGridEvent.subject
        
        # Extract blob information from the subject
        # Subject format: /blobServices/default/containers/{container}/blobs/{blob_name}
        blob_path = subject.split('/blobs/')[-1] if '/blobs/' in subject else ''
        blob_name = blob_path
        
        logger.info(f"Event Grid event received:")
        logger.info(f"  Event Type: {event_type}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  Blob Name: {blob_name}")
        logger.info(f"  Event Data: {event_data}")
        
        # Check if this is a documents container event
        if f"/containers/{settings.DOCUMENTS_CONTAINER_NAME}/" not in subject:
            logger.info(f"Ignoring event for non-documents container: {subject}")
            return
        
        # Handle blob deletion events
        if event_type == "Microsoft.Storage.BlobDeleted":
            logger.info(f"Processing blob deletion event for: {blob_name}")
            _handle_blob_deletion(blob_name)
            return
        
        # Handle blob creation/update events
        elif event_type == "Microsoft.Storage.BlobCreated":
            logger.info(f"Processing blob creation event for: {blob_name}")
            
            # Get blob information from event data
            blob_url = event_data.get('url', '')
            blob_size = event_data.get('contentLength', 0)
            content_type = event_data.get('contentType', 'application/octet-stream')
            
            # Check if file is supported
            is_supported, error_msg = document_processor.is_supported_file(blob_name, blob_size)
            if not is_supported:
                logger.info(f"Skipping unsupported file {blob_name}: {error_msg}")
                return
            
            # Download blob content using blob service client
            try:
                blob_service_client = get_blob_service_client()
                blob_client = blob_service_client.get_blob_client(
                    container=settings.DOCUMENTS_CONTAINER_NAME,
                    blob=blob_name
                )
                blob_content = blob_client.download_blob().readall()
                
                # Create document metadata
                metadata = document_processor.create_document_metadata(
                    blob_name=blob_name,
                    blob_url=blob_url,
                    container_name=settings.DOCUMENTS_CONTAINER_NAME,
                    file_size=blob_size,
                    content_type=content_type,
                    last_modified=datetime.utcnow()
                )
                
                # Check if document already exists and skip if not forcing reprocess
                if cosmos_manager.check_document_exists(metadata.id):
                    logger.info(f"Document {metadata.id} already exists, skipping processing")
                    return
                
                # Process the document
                _process_single_document(blob_content, metadata)
                
                logger.info(f"Successfully processed document: {blob_name}")
                
            except Exception as blob_error:
                logger.error(f"Error downloading blob {blob_name}: {blob_error}")
                return
        
        else:
            logger.info(f"Ignoring unsupported event type: {event_type}")
            return
        
    except Exception as e:
        logger.error(f"Error processing Event Grid event: {e}")
        logger.error(f"Event data: {eventGridEvent.get_json() if eventGridEvent else 'None'}")
        # Store error in metadata if possible
        try:
            if 'metadata' in locals():
                metadata.processing_status = ProcessingStatus.FAILED
                metadata.error_message = str(e)
                cosmos_manager.store_document_metadata(metadata)
        except:
            pass


def _handle_blob_deletion(blob_name: str) -> None:
    """
    Handle blob deletion by removing associated chunks and metadata from Cosmos DB.
    """
    try:
        # Generate document ID the same way as in create_document_metadata
        document_id = blob_name.replace('/', '_').replace(' ', '_')
        
        # Delete all chunks and metadata for this document
        success = cosmos_manager.delete_document(document_id)
        
        if success:
            logger.info(f"Successfully deleted document and chunks for: {blob_name} (ID: {document_id})")
        else:
            logger.warning(f"Document {document_id} not found in Cosmos DB for deletion")
            
    except Exception as e:
        logger.error(f"Error deleting document {blob_name} from Cosmos DB: {e}")
        # Don't re-raise since this shouldn't fail the entire trigger


@app.function_name("manual_process_documents")
@app.route(route="process-documents", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def manual_process_documents(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for manually processing documents.
    Useful for processing existing files or reindexing.
    """
    try:
        # Parse request
        try:
            req_body = req.get_json()
            job_request = ProcessingJobRequest(**req_body) if req_body else ProcessingJobRequest()
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": f"Invalid request: {e}"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        logger.info(f"Starting manual processing job {job_id}")
        
        # Initialize blob service client using DefaultAzureCredential
        blob_service_client = get_blob_service_client()
        
        # Get container client
        container_client = blob_service_client.get_container_client(job_request.container_name)
        
        # List blobs to process
        blobs_to_process = []
        for blob in container_client.list_blobs(name_starts_with=job_request.blob_prefix):
            # Check if file is supported
            is_supported, _ = document_processor.is_supported_file(blob.name, blob.size)
            if is_supported:
                blobs_to_process.append(blob)
        
        # Process documents
        job_status = ProcessingJobStatus(
            job_id=job_id,
            status=ProcessingStatus.PROCESSING,
            started_at=datetime.utcnow(),
            documents_processed=0,
            documents_failed=0
        )
        
        for blob in blobs_to_process:
            try:
                # Skip if document exists and not forcing reprocess
                document_id = blob.name.replace('/', '_').replace(' ', '_')
                if not job_request.force_reprocess and cosmos_manager.check_document_exists(document_id):
                    logger.info(f"Skipping existing document: {blob.name}")
                    continue
                
                # Download and process blob
                blob_client = container_client.get_blob_client(blob)
                blob_data = blob_client.download_blob().readall()
                
                # Create metadata
                metadata = document_processor.create_document_metadata(
                    blob_name=blob.name,
                    blob_url=blob_client.url,
                    container_name=job_request.container_name,
                    file_size=blob.size,
                    content_type=blob.content_settings.content_type or "application/octet-stream",
                    last_modified=blob.last_modified
                )
                
                # Filter by document type if specified
                if job_request.document_types and metadata.document_type not in job_request.document_types:
                    continue
                
                # Process document
                _process_single_document(blob_data, metadata)
                job_status.documents_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing blob {blob.name}: {e}")
                job_status.documents_failed += 1
        
        # Update job status
        job_status.status = ProcessingStatus.COMPLETED
        job_status.completed_at = datetime.utcnow()
        
        logger.info(f"Completed processing job {job_id}: {job_status.documents_processed} processed, {job_status.documents_failed} failed")
        
        return func.HttpResponse(
            json.dumps(job_status.model_dump(), default=str),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error in manual processing: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


def _process_single_document(file_content: bytes, metadata: DocumentMetadata) -> None:
    """
    Process a single document: convert to markdown, chunk, generate embeddings, and store.
    """
    try:
        # Update processing status
        metadata.processing_status = ProcessingStatus.PROCESSING
        
        # Process document into chunks
        chunks = document_processor.process_document(file_content, metadata)
        
        if not chunks:
            raise ValueError("No chunks created from document")
        
        # Generate embeddings for chunks
        chunks_with_embeddings = embedding_generator.add_embeddings_to_chunks(chunks)
        
        # Store chunks in Cosmos DB
        cosmos_manager.store_document_chunks(chunks_with_embeddings)
        
        # Update metadata with success status
        metadata.processing_status = ProcessingStatus.COMPLETED
        metadata.chunk_count = len(chunks_with_embeddings)
        
        # Store metadata
        cosmos_manager.store_document_metadata(metadata)
        
        logger.info(f"Successfully processed document {metadata.id} with {len(chunks_with_embeddings)} chunks")
        
    except Exception as e:
        logger.error(f"Error processing document {metadata.id}: {e}")
        
        # Update metadata with error status
        metadata.processing_status = ProcessingStatus.FAILED
        metadata.error_message = str(e)
        
        try:
            cosmos_manager.store_document_metadata(metadata)
        except Exception as store_error:
            logger.error(f"Error storing metadata for failed document {metadata.id}: {store_error}")
        
        raise
