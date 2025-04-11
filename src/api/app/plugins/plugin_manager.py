import asyncio
import logging
import importlib
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Type
from opentelemetry import trace

from semantic_kernel.functions.kernel_plugin import KernelPlugin
from app.config.config import get_settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class AgentPlugin(ABC):
    """Base class for all agent plugins that can be added to agents."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of the plugin."""
        pass
    
    @property
    def plugin_type(self) -> str:
        """Get the type of the plugin."""
        return self.__class__.__name__
    
    @abstractmethod
    async def initialize(self, **kwargs) -> bool:
        """Initialize the plugin with optional arguments."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Clean up any resources used by the plugin."""
        pass
    
    @abstractmethod
    def to_kernel_plugin(self) -> Any:
        """Convert the plugin to a format that can be added to a kernel or agent."""
        pass

class PluginManager:
    """Manager for dynamically creating and managing various types of plugins."""
    
    def __init__(self):
        """Initialize the plugin manager."""
        self.plugins: Dict[str, AgentPlugin] = {}
        self.settings = get_settings()
        self._plugin_registry: Dict[str, Type[AgentPlugin]] = {}
        self._register_plugin_types()
    
    def _register_plugin_types(self):
        """Register all available plugin types."""
        try:
            # Import plugin types
            from app.plugins.mcp_plugin import MCPPlugin
            from app.plugins.openapi_plugin import OpenAPIPlugin
            # from app.plugins.agent_plugin import AgentAsPlugin
            # from app.plugins.azure_plugin import AzureAIServicesPlugin
            
            # Register them with the manager
            self._plugin_registry["mcp"] = MCPPlugin
            self._plugin_registry["openapi"] = OpenAPIPlugin
            # self._plugin_registry["agent"] = AgentAsPlugin
            # self._plugin_registry["azure"] = AzureAIServicesPlugin
            
            logger.info(f"Registered {len(self._plugin_registry)} plugin types")
        except ImportError as e:
            logger.warning(f"Some plugin types could not be registered: {str(e)}")
    
    async def create_plugin(self, plugin_type: str, config: Dict[str, Any], **kwargs) -> Optional[AgentPlugin]:
        """Create a plugin of the specified type with the given configuration."""
        with tracer.start_as_current_span(f"create_plugin_{plugin_type}"):
            if plugin_type not in self._plugin_registry:
                logger.warning(f"Unknown plugin type: {plugin_type}")
                return None
            
            try:
                # Create plugin instance
                plugin_class = self._plugin_registry[plugin_type]
                plugin = plugin_class()
                
                # Initialize the plugin
                success = await plugin.initialize(config=config, **kwargs)
                if not success:
                    logger.warning(f"Failed to initialize {plugin_type} plugin")
                    await plugin.close()
                    return None
                
                # Generate a unique ID for this plugin instance
                plugin_id = f"{plugin_type}_{id(plugin)}"
                self.plugins[plugin_id] = plugin
                
                logger.info(f"Successfully created {plugin_type} plugin: {plugin.name}")
                return plugin
            except Exception as e:
                logger.error(f"Error creating {plugin_type} plugin: {str(e)}", exc_info=True)
                return None
    
    async def create_plugins_from_agent_config(self, agent_config: Any, session_id: str = None) -> List[AgentPlugin]:
        """Create plugins based on the agent configuration."""
        with tracer.start_as_current_span("create_plugins_from_agent_config"):
            created_plugins = []
            
            if not hasattr(agent_config, "tools") or not agent_config.tools:
                logger.info("No tools defined in agent configuration")
                return created_plugins
            
            for tool in agent_config.tools:
                plugin = await self._create_plugin_from_tool(tool, session_id)
                if plugin:
                    created_plugins.append(plugin)
            
            logger.info(f"Created {len(created_plugins)} plugins from agent configuration")
            return created_plugins
    
    async def _create_plugin_from_tool(self, tool: Any, session_id: str = None) -> Optional[AgentPlugin]:
        """Create a plugin from a tool definition."""
        try:
            tool_type = tool.type.lower()
            
            # Handle different tool types
            if tool_type == "modelcontextprotocol" and hasattr(tool, "mcpDefinition"):
                # MCP plugin
                return await self.create_plugin(
                    "mcp", 
                    config=tool.mcpDefinition,
                    session_id=session_id
                )
            elif tool_type == "openapi" and hasattr(tool, "openApiDefinition"):
                # OpenAPI plugin
                return await self.create_plugin(
                    "openapi", 
                    config=tool.openApiDefinition,
                    session_id=session_id
                )
            elif tool_type == "agent" and hasattr(tool, "agentDefinition"):
                # Agent as plugin
                return await self.create_plugin(
                    "agent", 
                    config=tool.agentDefinition,
                    session_id=session_id
                )
            elif tool_type == "azureai" and hasattr(tool, "azureDefinition"):
                # Azure AI Services plugin
                return await self.create_plugin(
                    "azure", 
                    config=tool.azureDefinition,
                    session_id=session_id
                )
            else:
                logger.warning(f"Unsupported tool type: {tool_type}")
                return None
        except Exception as e:
            logger.error(f"Error creating plugin from tool: {str(e)}", exc_info=True)
            return None
    
    async def close_all(self):
        """Close all plugins managed by this plugin manager."""
        with tracer.start_as_current_span("close_all_plugins"):
            close_tasks = []
            
            for plugin_id, plugin in list(self.plugins.items()):
                try:
                    # Schedule plugin closure
                    close_tasks.append(plugin.close())
                    logger.info(f"Scheduled cleanup for plugin: {plugin.name}")
                except Exception as e:
                    logger.warning(f"Error scheduling cleanup for plugin {plugin_id}: {str(e)}")
            
            # Wait for all plugins to close
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            
            # Clear the plugins dictionary
            self.plugins.clear()
            logger.info("All plugins closed")
    
    async def close_plugin(self, plugin_id: str) -> bool:
        """Close a specific plugin by ID."""
        if plugin_id not in self.plugins:
            logger.warning(f"Plugin not found: {plugin_id}")
            return False
        
        try:
            plugin = self.plugins[plugin_id]
            await plugin.close()
            del self.plugins[plugin_id]
            logger.info(f"Closed plugin: {plugin.name}")
            return True
        except Exception as e:
            logger.error(f"Error closing plugin {plugin_id}: {str(e)}")
            return False
    
    def get_kernel_plugins(self) -> List[Any]:
        """Get all plugins in a format that can be added to a kernel."""
        return [plugin.to_kernel_plugin() for plugin in self.plugins.values()]
        pass