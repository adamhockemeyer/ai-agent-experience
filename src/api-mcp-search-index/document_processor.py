"""
Document processing utilities using MarkItDown.
"""
import logging
import os
import tempfile
from typing import List, Optional, Tuple
from io import BytesIO

from markitdown import MarkItDown
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

from models import DocumentType, DocumentMetadata, DocumentChunk
from config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes documents using MarkItDown and creates chunks."""
    
    def __init__(self):
        """Initialize the document processor."""
        self.markitdown = self._create_markitdown_instance()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Could not load tokenizer: {e}. Token counts will be estimated.")
            self.tokenizer = None
    
    def _create_markitdown_instance(self) -> MarkItDown:
        """Create MarkItDown instance with optional configurations."""
        kwargs = {}
        
        # Add Azure Document Intelligence endpoint if configured
        if settings.AZURE_DOC_INTELLIGENCE_ENDPOINT:
            kwargs["docintel_endpoint"] = settings.AZURE_DOC_INTELLIGENCE_ENDPOINT
            logger.info("MarkItDown configured with Azure Document Intelligence")
        
        # Add LLM client for image descriptions if configured
        if settings.LLM_CLIENT_ENDPOINT and settings.LLM_MODEL:
            try:
                from openai import AzureOpenAI
                
                # Use API key if provided, otherwise use Azure AD token provider
                if settings.AZURE_OPENAI_KEY:
                    client = AzureOpenAI(
                        azure_endpoint=settings.LLM_CLIENT_ENDPOINT,
                        api_version=settings.AZURE_OPENAI_API_VERSION,
                        api_key=settings.AZURE_OPENAI_KEY
                    )
                else:
                    client = AzureOpenAI(
                        azure_endpoint=settings.LLM_CLIENT_ENDPOINT,
                        api_version=settings.AZURE_OPENAI_API_VERSION,
                        azure_ad_token_provider=self._get_token_provider()
                    )
                    
                kwargs["llm_client"] = client
                kwargs["llm_model"] = settings.LLM_MODEL
                logger.info(f"MarkItDown configured with LLM client: {settings.LLM_MODEL}")
            except Exception as e:
                logger.warning(f"Could not configure LLM client: {e}")
        
        return MarkItDown(**kwargs)
    
    def _get_token_provider(self):
        """Get Azure AD token provider for OpenAI client."""
        from azure.identity import DefaultAzureCredential
        
        credential = DefaultAzureCredential()
        
        def get_token():
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        
        return get_token
    
    def determine_document_type(self, blob_name: str) -> str:
        """Determine document type based on folder structure."""
        return DocumentType.from_blob_path(blob_name)
    
    def is_supported_file(self, blob_name: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Check if file is supported for processing."""
        # Check file size
        if file_size > settings.max_file_size_bytes:
            return False, f"File size ({file_size} bytes) exceeds maximum ({settings.max_file_size_bytes} bytes)"
        
        # Check file extension
        file_extension = os.path.splitext(blob_name.lower())[1]
        if file_extension not in settings.supported_extensions_list:
            return False, f"File extension '{file_extension}' is not supported"
        
        return True, None
    
    def process_document(self, file_content: bytes, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """Process a document and return chunks."""
        try:
            # Convert document to markdown
            markdown_content = self._convert_to_markdown(file_content, metadata.blob_name)
            
            if not markdown_content.strip():
                raise ValueError("No content extracted from document")
            
            # Split into chunks
            chunks = self._create_chunks(markdown_content, metadata)
            
            logger.info(f"Successfully processed document {metadata.blob_name} into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing document {metadata.blob_name}: {e}")
            raise
    
    def _convert_to_markdown(self, file_content: bytes, blob_name: str) -> str:
        """Convert file content to markdown using MarkItDown."""
        # Create temporary file for MarkItDown processing
        file_extension = os.path.splitext(blob_name.lower())[1]
        
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            result = self.markitdown.convert(temp_file_path)
            return result.text_content
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Could not delete temporary file {temp_file_path}: {e}")
    
    def _create_chunks(self, content: str, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """Split content into chunks and create DocumentChunk objects."""
        # Split text into chunks
        text_chunks = self.text_splitter.split_text(content)
        
        chunks = []
        char_position = 0
        
        for i, chunk_text in enumerate(text_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            
            # Calculate token count
            token_count = self._count_tokens(chunk_text)
            
            # Skip chunks that are too large
            if token_count > settings.MAX_TOKENS_PER_CHUNK:
                logger.warning(f"Chunk {i} for document {metadata.blob_name} has {token_count} tokens, skipping")
                continue
            
            # Create chunk ID
            chunk_id = f"{metadata.id}_chunk_{i:04d}"
            
            # Calculate character positions
            start_char = char_position
            end_char = start_char + len(chunk_text)
            char_position = end_char
            
            chunk = DocumentChunk(
                id=chunk_id,
                document_id=metadata.id,
                chunk_index=i,
                content=chunk_text,
                content_length=len(chunk_text),
                token_count=token_count,
                embedding=[],  # Will be populated by embedding generator
                blob_url=metadata.blob_url,
                blob_name=metadata.blob_name,
                document_type=metadata.document_type,
                file_extension=metadata.file_extension,
                processed_at=metadata.processed_at,
                start_char=start_char,
                end_char=end_char
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            try:
                return len(self.tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"Error counting tokens: {e}")
        
        # Fallback: estimate 4 characters per token
        return len(text) // 4
    
    def create_document_metadata(
        self, 
        blob_name: str, 
        blob_url: str, 
        container_name: str,
        file_size: int,
        content_type: str,
        last_modified
    ) -> DocumentMetadata:
        """Create document metadata from blob information."""
        # Generate document ID from blob name
        document_id = blob_name.replace('/', '_').replace(' ', '_')
        
        return DocumentMetadata(
            id=document_id,
            blob_url=blob_url,
            blob_name=blob_name,
            container_name=container_name,
            document_type=self.determine_document_type(blob_name),
            file_extension=os.path.splitext(blob_name.lower())[1],
            file_size=file_size,
            content_type=content_type,
            last_modified=last_modified
        )
