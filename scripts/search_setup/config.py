"""
Configuration module for Azure AI Search multi-index setup.
Handles authentication and common settings for search resources.
"""
import os
import logging
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_env_var(var_name, default=None, required=True):
    """Get environment variable or raise exception if required and not found."""
    value = os.environ.get(var_name, default)
    if value is None and required:
        raise ValueError(f"Environment variable '{var_name}' is required but not set.")
    return value

# Load configuration from environment variables
try:
    SEARCH_SERVICE_NAME = get_env_var("AZURE_SEARCH_SERVICE_NAME")
    SEARCH_SERVICE_ENDPOINT = f"https://{SEARCH_SERVICE_NAME}.search.windows.net"
    STORAGE_ACCOUNT_NAME = get_env_var("AZURE_STORAGE_ACCOUNT_NAME")
    STORAGE_ENDPOINT = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    BLOB_CONTAINER_NAME = get_env_var("BLOB_CONTAINER_NAME", "documents")
    OPENAI_ENDPOINT = get_env_var("AZURE_OPENAI_ENDPOINT")
    OPENAI_EMBEDDING_DEPLOYMENT = get_env_var("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small", required=False)
    SEMANTIC_CONFIG_NAME = get_env_var("SEMANTIC_CONFIG_NAME", "default", required=False)
    VECTOR_SEARCH_CONFIG_NAME = get_env_var("VECTOR_SEARCH_CONFIG_NAME", "default", required=False)
    
    # Default vectors dimensions for embedding model
    EMBEDDING_DIMENSIONS = int(get_env_var("EMBEDDING_DIMENSIONS", "1536", required=False))
    
except ValueError as e:
    logger.error(f"Configuration error: {str(e)}")
    raise

def get_credentials():
    """Get Azure credentials using Managed Identity."""
    try:
        # Try managed identity first (for Azure-hosted environments)
        credential = ManagedIdentityCredential()
        # Test the credential
        credential.get_token("https://management.azure.com/.default")
        logger.info("Using Managed Identity for authentication")
        return credential
    except Exception as e:
        logger.info(f"Managed Identity not available: {str(e)}")
        try:
            # Fall back to DefaultAzureCredential which includes environment, managed identity, and interactive
            credential = DefaultAzureCredential()
            credential.get_token("https://management.azure.com/.default")
            logger.info("Using DefaultAzureCredential for authentication")
            return credential
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise

def generate_index_name(folder_name):
    """Generate a valid index name from folder name."""
    # Remove any non-alphanumeric characters and convert to lowercase
    clean_name = ''.join(c for c in folder_name if c.isalnum())
    return f"{clean_name.lower()}-index"

def generate_datasource_name(folder_name):
    """Generate a valid datasource name from folder name."""
    clean_name = ''.join(c for c in folder_name if c.isalnum())
    return f"{clean_name.lower()}-datasource"

def generate_skillset_name(folder_name):
    """Generate a valid skillset name from folder name."""
    clean_name = ''.join(c for c in folder_name if c.isalnum())
    return f"{clean_name.lower()}-skillset"

def generate_indexer_name(folder_name):
    """Generate a valid indexer name from folder name."""
    clean_name = ''.join(c for c in folder_name if c.isalnum())
    return f"{clean_name.lower()}-indexer"