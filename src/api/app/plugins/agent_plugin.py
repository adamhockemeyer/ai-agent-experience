# app/plugins/agent_plugin.py
import logging
from typing import Any, Optional, Dict, List
from app.models import Tool, Agent
from app.plugins.base import PluginBase
from app.config.azure_app_config import AzureAppConfig
from app.agents.agent_factory import AgentFactory
from app.services.kernel_factory import KernelFactory
from app.config.config import get_settings

logger = logging.getLogger(__name__)

class AgentPluginHandler(PluginBase):
    """Handler for using other Semantic Kernel agents as plugins."""
    
    def __init__(self):
        """Initialize the agent plugin handler."""
        self._agent_plugins = {}  # Store created agents by ID
        self._config_client = AzureAppConfig(
            connection_string=get_settings().azure_app_config_connection_string,
            endpoint=get_settings().azure_app_config_endpoint
        )
    
    async def initialize(self, tool: Tool, plugin_manager=None, agent_id=None, **kwargs) -> Any:
        """Initialize an agent as a plugin using the agent ID."""
        if tool.type != "Agent":
            return None
            
        try:
            nested_agent_id = tool.id
            logger.info(f"Initializing agent plugin with ID: {nested_agent_id}{' for parent agent: ' + agent_id if agent_id else ''}")
            
            # Get agent configuration
            try:
                agent_config = await self._config_client.get(key=nested_agent_id, model_type=Agent, prefix="agent:")
            except Exception as e:
                logger.error(f"Error retrieving agent configuration: {str(e)}")
                return None
            
            # Create kernel for this agent plugin 
            kernel = await KernelFactory.create_kernel(agent_config)
            
            # Initialize plugins for this nested agent
            plugins = []
            if agent_config.tools:
                try:
                    # Use the provided plugin_manager if available, else create a new one
                    if plugin_manager is not None:
                        plugins = await plugin_manager.initialize_plugins(agent_config)
                    else:
                        from app.plugins.plugin_manager import PluginManager
                        async with PluginManager() as new_plugin_manager:
                            plugins = await new_plugin_manager.initialize_plugins(agent_config)
                    logger.info(f"Initialized {len(plugins)} plugins for nested agent: {agent_id}")
                except Exception as e:
                    logger.error(f"Error initializing plugins for nested agent {agent_id}: {str(e)}")
            
            # Create agent with its plugins
            agent, thread = await AgentFactory.create_agent(kernel, agent_config, plugins)
            
            # Store reference with compound key
            plugin_key = f"{agent_id}:{tool.id}" if agent_id else tool.id
            self._agent_plugins[plugin_key] = {
                "agent": agent,
                "kernel": kernel,
                "thread": thread
            }
            logger.debug(f"Stored agent plugin with key: {plugin_key}")
            
            # Return the agent itself - Semantic Kernel agents implement KernelPlugin interface
            return agent
            
        except Exception as e:
            logger.error(f"Error initializing agent plugin: {str(e)}", exc_info=True)
            return None
    
    async def get_kernel_plugin(self, agent: Any) -> Any:
        """
        Return the agent directly - newer versions of Semantic Kernel agents 
        already implement KernelPlugin interface.
        """
        if not agent:
            return None
        
        # Just return the agent directly - it already implements the KernelPlugin interface
        return agent
    
    async def cleanup(self, agent: Any) -> None:
        """Clean up resources used by the agent plugin."""
        if not agent:
            return
        
        try:
            # Find the agent using value lookup
            plugin_key = None
            for key, info in self._agent_plugins.items():
                if info["agent"] == agent:
                    plugin_key = key
                    break
            
            if plugin_key:
                # Extract agent info for logging
                agent_info = ""
                if ":" in plugin_key:
                    parent_agent_id = plugin_key.split(":", 1)[0]
                    agent_info = f" from parent agent {parent_agent_id}"
                
                # Clean up the agent
                if hasattr(agent, "cleanup"):
                    await agent.cleanup()
                
                # Remove from cache
                del self._agent_plugins[plugin_key]
                logger.info(f"Cleaned up agent plugin: {plugin_key.split(':')[-1]}{agent_info}")
                
        except Exception as e:
            logger.error(f"Error cleaning up agent plugin: {str(e)}", exc_info=True)