"""
Module to discover document folders and structures from blob storage.
"""
import os
import logging
from azure.storage.blob import BlobServiceClient, ContainerClient
from config import get_credentials, STORAGE_ENDPOINT, BLOB_CONTAINER_NAME

logger = logging.getLogger(__name__)

def get_blob_service_client():
    """Get a blob service client using managed identity."""
    credential = get_credentials()
    return BlobServiceClient(account_url=STORAGE_ENDPOINT, credential=credential)

def get_document_folders():
    """
    Discover document folders in blob storage.
    Returns a list of folder names.
    """
    try:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        
        # List all blobs in the container
        blobs = container_client.list_blobs()
        
        # Extract folder paths from blob names
        folders = set()
        for blob in blobs:
            # Skip if it's not in a subfolder
            if '/' not in blob.name:
                continue
            
            # Get the top-level folder
            folder = blob.name.split('/')[0]
            folders.add(folder)
        
        logger.info(f"Discovered document folders: {', '.join(folders)}")
        return list(folders)
        
    except Exception as e:
        logger.error(f"Error discovering document folders: {str(e)}")
        raise

def get_folder_blob_prefix(folder_name):
    """Get the blob prefix for a specific folder."""
    return f"{folder_name}/"

def get_local_document_folders(documents_path):
    """
    Discover document folders in local file system.
    Used during development or when running from local machine.
    Returns a list of folder names.
    """
    try:
        if not os.path.exists(documents_path):
            logger.warning(f"Documents path '{documents_path}' does not exist")
            return []
        
        # Get list of directories in the documents folder
        folders = [item for item in os.listdir(documents_path) 
                  if os.path.isdir(os.path.join(documents_path, item))]
        
        logger.info(f"Discovered local document folders: {', '.join(folders)}")
        return folders
        
    except Exception as e:
        logger.error(f"Error discovering local document folders: {str(e)}")
        raise