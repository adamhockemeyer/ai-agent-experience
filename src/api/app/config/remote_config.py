from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Any, Type

T = TypeVar('T')

class RemoteConfig(Generic[T], ABC):
    """Base class for remote configuration with CRUD operations."""
    
    def __init__(self):
        """Initialize remote configuration."""
        pass
    
    @abstractmethod
    async def get(self, key: str, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> T:
        """
        Get configuration value for the specified key.
        
        Args:
            key: The configuration key
            model_type: The type of the configuration value
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def delete(self, key: str, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> None:
        """
        Delete configuration value for the specified key.
        
        Args:
            key: The configuration key
            model_type: The type of the configuration value
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        pass
    
    @abstractmethod
    async def list(self, model_type: Type[T], prefix: Optional[str] = None, label: Optional[str] = None) -> List[T]:
        """
        List all configuration values with the specified prefix.
        
        Args:
            model_type: The type of the configuration values
            prefix: Optional prefix for the configuration
            label: Optional label for the configuration
        """
        pass
