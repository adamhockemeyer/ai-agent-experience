from fastapi import Depends
from typing import Optional,TypeVar, Type
from pydantic import BaseModel

from app.services.chat_service import ChatService
from app.config.azure_app_config import AzureAppConfig
from app.config.remote_config import RemoteConfig
from app.models import Agent
from app.config import  get_settings

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


def get_chat_service() -> ChatService:
    """
    Get the chat service.
    """

    return ChatService()