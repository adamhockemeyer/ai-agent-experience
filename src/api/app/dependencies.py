from fastapi import Depends
from typing import Optional,TypeVar, Type
from pydantic import BaseModel

from app.services.chat_service import ChatService
from app.config.azure_app_config import AzureAppConfig
from app.config.remote_config import RemoteConfig
from app.models import Agent
from app.config import get_settings
from app.services.thread_storage import ThreadStorage, InMemoryThreadStorage, RedisThreadStorage, CosmosDbThreadStorage

T = TypeVar('T', bound=BaseModel)


def get_remote_config() -> RemoteConfig[T]:
    """
    Dependency provider for RemoteConfig.
    
    Returns an instance of AzureAppConfig that honors the RemoteConfig interface.
    
    Args:
        prefix: Optional prefix for configuration keys
        label: Optional label for configuration environments
        
    Returns:
        A properly configured RemoteConfig instance
    """
    return AzureAppConfig(
        connection_string=get_settings().azure_app_config_connection_string,
        endpoint=get_settings().azure_app_config_endpoint
    )


def get_thread_storage() -> ThreadStorage:
    """
    Get the appropriate thread storage implementation based on configuration.
    """
    # Get application settings
    settings = get_settings()
    
    # Initialize storage based on configuration
    storage_type = settings.thread_storage_type.lower()
    
    if storage_type == "redis":
        return RedisThreadStorage(
            connection_string=settings.redis_connection_string,
            ttl_seconds=settings.thread_ttl_seconds
        )
    elif storage_type == "cosmosdb":
        return CosmosDbThreadStorage(
            connection_string=settings.cosmos_db_connection_string,
            endpoint=settings.cosmos_db_endpoint,
            database_name=settings.cosmos_db_database_name,
            container_name=settings.cosmos_db_container_name,
            partition_key=settings.cosmos_db_partition_key,
            ttl_seconds=settings.thread_ttl_seconds
        )
    else:  # Default to memory storage
        return InMemoryThreadStorage()


def get_chat_service() -> ChatService:
    """
    Get the chat service with appropriate thread storage.
    """
    thread_storage = get_thread_storage()
    return ChatService(thread_storage)