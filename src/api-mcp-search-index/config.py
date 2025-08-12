"""
Configuration settings for the Azure Functions app.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Azure Storage settings
    STORAGE_CONNECTION_STRING: str = Field(default="UseDevelopmentStorage=true", env="AzureWebJobsStorage")
    DOCUMENTS_STORAGE_CONNECTION_STRING: Optional[str] = Field(default=None, env="DOCUMENTS_STORAGE_CONNECTION_STRING")
    DOCUMENTS_STORAGE_ACCOUNT_URL: str = Field(default="", env="DOCUMENTS_STORAGE_ACCOUNT_URL")
    DOCUMENTS_CONTAINER_NAME: str = Field(default="documents", env="DOCUMENTS_CONTAINER_NAME")
    
    # Managed Identity settings for blob trigger (prefix-based configuration)
    # These allow the blob trigger to use managed identity instead of connection strings
    
    # Azure Cosmos DB settings
    COSMOS_ENDPOINT: str = Field(default="https://localhost:8081", env="COSMOS_ENDPOINT")
    COSMOS_KEY: Optional[str] = Field(default=None, env="COSMOS_KEY")
    COSMOS_DATABASE_NAME: str = Field(default="DocumentIndex", env="COSMOS_DATABASE_NAME")
    COSMOS_CONTAINER_NAME: str = Field(default="chunks", env="COSMOS_CONTAINER_NAME")
    
    # Azure subscription and resource group for management operations
    AZURE_SUBSCRIPTION_ID: Optional[str] = Field(default=None, env="AZURE_SUBSCRIPTION_ID")
    AZURE_RESOURCE_GROUP: Optional[str] = Field(default=None, env="AZURE_RESOURCE_GROUP")
    
    # Azure OpenAI settings for embeddings
    AZURE_OPENAI_ENDPOINT: str = Field(default="https://localhost:8080", env="AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_KEY: Optional[str] = Field(default=None, env="AZURE_OPENAI_KEY")
    AZURE_OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-ada-002", env="AZURE_OPENAI_EMBEDDING_MODEL")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-02-01", env="AZURE_OPENAI_API_VERSION")
    
    # MarkItDown optional settings
    AZURE_DOC_INTELLIGENCE_ENDPOINT: Optional[str] = Field(default=None, env="AZURE_DOC_INTELLIGENCE_ENDPOINT")
    LLM_CLIENT_ENDPOINT: Optional[str] = Field(default=None, env="LLM_CLIENT_ENDPOINT")
    LLM_MODEL: Optional[str] = Field(default="gpt-4o", env="LLM_MODEL")
    
    # Text processing settings
    CHUNK_SIZE: int = Field(default=1000, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=200, env="CHUNK_OVERLAP")
    MAX_TOKENS_PER_CHUNK: int = Field(default=8000, env="MAX_TOKENS_PER_CHUNK")
    
    # Embedding settings
    EMBEDDING_BATCH_SIZE: int = Field(default=16, env="EMBEDDING_BATCH_SIZE")
    EMBEDDING_DIMENSIONS: int = Field(default=1536, env="EMBEDDING_DIMENSIONS")
    
    # Processing settings
    MAX_FILE_SIZE_MB: int = Field(default=100, env="MAX_FILE_SIZE_MB")
    SUPPORTED_EXTENSIONS: str = Field(
        default=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.html,.xlsx,.xls,.csv,.rtf,.odt,.png,.jpg,.jpeg,.bmp,.tiff,.gif",
        env="SUPPORTED_EXTENSIONS"
    )
    
    # Retry settings
    MAX_RETRIES: int = Field(default=3, env="MAX_RETRIES")
    RETRY_DELAY_SECONDS: int = Field(default=1, env="RETRY_DELAY_SECONDS")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def supported_extensions_list(self) -> list[str]:
        """Get supported file extensions as a list."""
        return [ext.strip().lower() for ext in self.SUPPORTED_EXTENSIONS.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


# Global settings instance
settings = Settings()
