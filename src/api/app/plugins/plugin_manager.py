# app/plugins/plugin_manager.py
from typing import Dict, List, Any, Optional
from app.models import Tool, Agent
from app.plugins.base import PluginBase
from app.plugins.mcp_plugin import MCPPluginHandler
from app.plugins.openapi_plugin import OpenAPIPluginHandler
from app.plugins.agent_plugin import AgentPluginHandler

class PluginManager:
    """Manages the lifecycle of plugins for an agent."""
    
    def __init__(self):
        self._plugin_handlers = {
            "ModelContextProtocol": MCPPluginHandler(),
            "OpenAPI": OpenAPIPluginHandler(),
            "Agent": AgentPluginHandler()
        }
        self._active_plugins = []
        
    async def __aenter__(self):
        """Context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with proper plugin cleanup"""
        await self.cleanup_all_plugins()
        
    async def initialize_plugins(self, agent: Agent) -> List[Any]:
        """Initialize all plugins defined in agent configuration."""
        plugins = []
        
        for tool in agent.tools:
            if tool.type in self._plugin_handlers:
                handler = self._plugin_handlers[tool.type]
                # Initialize the plugin with the tool configuration
                plugin_data = await handler.initialize(tool)
                if plugin_data:
                    # Store both the handler and the plugin data for cleanup
                    self._active_plugins.append((handler, plugin_data))
                    # Get the kernel plugin representation
                    kernel_plugin = await handler.get_kernel_plugin(plugin_data)
                    if kernel_plugin:
                        plugins.append(kernel_plugin)
        
        return plugins
        
    async def cleanup_all_plugins(self):
        """Clean up all active plugins."""
        for handler, plugin_data in self._active_plugins:
            try:
                await handler.cleanup(plugin_data)
            except Exception as e:
                # Log but continue cleanup
                print(f"Error cleaning up plugin: {e}")
                
        self._active_plugins = []