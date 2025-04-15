# app/plugins/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import semantic_kernel as sk

class PluginBase(ABC):
    """Base class for all plugins to implement."""
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> Any:
        """Initialize the plugin with configuration."""
        pass
        
    @abstractmethod
    async def get_kernel_plugin(self) -> Any:
        """Return the plugin in a format suitable for Semantic Kernel."""
        pass
        
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources used by the plugin."""
        pass