"""
Embedding generation utilities using Azure OpenAI.
"""
import logging
import asyncio
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from azure.identity import DefaultAzureCredential
from azure.ai.textanalytics import TextAnalyticsClient

from models import DocumentChunk
from config import settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings using Azure OpenAI."""
    
    def __init__(self):
        """Initialize the embedding generator."""
        self.credential = DefaultAzureCredential()
        self._openai_client = None
    
    @property
    def openai_client(self):
        """Lazy initialization of Azure OpenAI client."""
        if self._openai_client is None:
            from openai import AzureOpenAI
            
            # Use API key if provided, otherwise use Azure AD token provider
            if settings.AZURE_OPENAI_KEY:
                self._openai_client = AzureOpenAI(
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    api_key=settings.AZURE_OPENAI_KEY
                )
            else:
                self._openai_client = AzureOpenAI(
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    azure_ad_token_provider=self._get_token_provider()
                )
        return self._openai_client
    
    def _get_token_provider(self):
        """Get Azure AD token provider for OpenAI client."""
        def get_token():
            token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        
        return get_token
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_DELAY_SECONDS, min=1, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model=settings.AZURE_OPENAI_EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_DELAY_SECONDS, min=1, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        try:
            # Process in smaller batches to avoid rate limits
            batch_size = settings.EMBEDDING_BATCH_SIZE
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = self.openai_client.embeddings.create(
                    input=batch,
                    model=settings.AZURE_OPENAI_EMBEDDING_MODEL
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.info(f"Generated embeddings for batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
    
    def generate_query_embedding(self, query_text: str) -> List[float]:
        """Generate embedding for search query."""
        return self.generate_embedding(query_text)
    
    def add_embeddings_to_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Add embeddings to document chunks."""
        if not chunks:
            return chunks
        
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        
        # Extract text content
        texts = [chunk.content for chunk in chunks]
        
        # Generate embeddings in batch
        embeddings = self.generate_embeddings_batch(texts)
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        logger.info(f"Successfully generated embeddings for {len(chunks)} chunks")
        return chunks
    
    def validate_embedding_dimensions(self, embedding: List[float]) -> bool:
        """Validate that embedding has correct dimensions."""
        expected_dim = settings.EMBEDDING_DIMENSIONS
        actual_dim = len(embedding)
        
        if actual_dim != expected_dim:
            logger.error(f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}")
            return False
        
        return True
