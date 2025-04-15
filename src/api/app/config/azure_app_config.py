import json
from typing import TypeVar, Optional, List, Type, Any
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential
from azure.appconfiguration import AzureAppConfigurationClient, ConfigurationSetting
from azure.core.exceptions import ResourceNotFoundError

from app.config.remote_config import RemoteConfig
from app.config import get_settings

T = TypeVar('T', bound=BaseModel)

class AzureAppConfig(RemoteConfig[T]):
    """Azure App Configuration implementation of RemoteConfig."""
    
    def __init__(self, connection_string: Optional[str] = None, endpoint: Optional[str] = None):
        """
        Initialize Azure App Configuration client.
        
        Args:
            connection_string: Connection string to the Azure App Configuration instance.
                               If not provided, DefaultAzureCredential will be used.
            endpoint: The Azure App Configuration endpoint URL. 
                      Required when using DefaultAzureCredential.
        """
        super().__init__()
        self.connection_string = connection_string
        self.endpoint = endpoint
        
    def _get_client(self) -> AzureAppConfigurationClient:
        """
        Get Azure App Configuration client using either connection string or DefaultAzureCredential.
        
        Returns:
            AzureAppConfigurationClient instance
        """
        if self.connection_string:
            return AzureAppConfigurationClient.from_connection_string(self.connection_string)
        elif self.endpoint:
            credential = DefaultAzureCredential()
            return AzureAppConfigurationClient(base_url=self.endpoint, credential=credential)
        else:
            raise ValueError("Either connection_string or endpoint must be provided")
    
    async def get(self, key: str, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> T:
        """
        Get configuration value for the specified key.
        
        Args:
            key: The configuration key
            model_type: The type of the configuration value
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        client = self._get_client()
        key_with_prefix = f"{prefix}{key}" if prefix else key
        try:
            config_setting = client.get_configuration_setting(
                key=key_with_prefix,
                label=label
            )
            # Convert the value to the specified model type
            value_dict = json.loads(config_setting.value)
            return model_type.parse_obj(value_dict)
        except ResourceNotFoundError:
            raise KeyError(f"Configuration key '{key_with_prefix}' not found")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve configuration key '{key_with_prefix}': {str(e)}")
    
    async def set(self, key: str, value: T, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> None:
        """
        Set configuration value for the specified key.
        
        Args:
            key: The configuration key
            value: The configuration value
            model_type: The type of the configuration value
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        client = self._get_client()
        key_with_prefix = f"{prefix}{key}" if prefix else key
        # Convert value to storeable format
        value_json = value.json()
        client.set_configuration_setting(
            key=key_with_prefix,
            value=value_json,
            label=label
        )
    
    async def delete(self, key: str, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> None:
        """
        Delete configuration value for the specified key.
        
        Args:
            key: The configuration key
            model_type: The type of the configuration value
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        client = self._get_client()
        key_with_prefix = f"{prefix}{key}" if prefix else key
        client.delete_configuration_setting(
            key=key_with_prefix,
            label=label
        )
    
    async def list(self, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> List[T]:
        """
        List all configuration values with the specified prefix.
        
        Args:
            model_type: The type of the configuration values
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        client = self._get_client()
        settings = client.list_configuration_settings(
            key_filter=f"{prefix}*" if prefix else None,
            label_filter=label
        )
        
        result = []
        # The settings object is an ItemPaged which is not async-iterable
        # Iterate through it synchronously
        for setting in settings:
            try:
                # Convert each setting to the specified model type
                value_dict = json.loads(setting.value)
                result.append(model_type.parse_obj(value_dict))
            except Exception as e:
                # Log error but continue with other settings
                print(f"Error parsing setting {setting.key}: {str(e)}")
            
        return result
