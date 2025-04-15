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
    
    async def initialize(self, tool: Tool) -> Any:
        """Initialize an agent as a plugin using the agent ID."""
        if tool.type != "Agent":
            return None
            
        try:
            agent_id = tool.id
            logger.info(f"Initializing agent plugin with ID: {agent_id}")
            
            # Get agent configuration
            try:
                agent_config = await self._config_client.get(key=agent_id, model_type=Agent, prefix="agent:")
            except Exception as e:
                logger.error(f"Error retrieving agent configuration: {str(e)}")
                return None
            
            # Create kernel for this agent plugin 
            kernel = await KernelFactory.create_kernel(agent_config)
            
            # Initialize plugins for this nested agent
            plugins = []
            if agent_config.tools:
                try:
                    # Import here to avoid circular imports
                    from app.plugins.plugin_manager import PluginManager
                    async with PluginManager() as plugin_manager:
                        plugins = await plugin_manager.initialize_plugins(agent_config)
                        logger.info(f"Initialized {len(plugins)} plugins for nested agent: {agent_id}")
                except Exception as e:
                    logger.error(f"Error initializing plugins for nested agent {agent_id}: {str(e)}")
            
            # Create agent with its plugins
            agent, thread = await AgentFactory.create_agent(kernel, agent_config, plugins)
            
            # Store reference for cleanup
            self._agent_plugins[agent_id] = {
                "agent": agent,
                "kernel": kernel,
                "thread": thread
            }
            
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
            # Find the agent ID
            agent_id = None
            for aid, info in self._agent_plugins.items():
                if info["agent"] == agent:
                    agent_id = aid
                    break
            
            if agent_id:
                # Clean up the agent
                if hasattr(agent, "cleanup"):
                    await agent.cleanup()
                
                # Remove from cache
                del self._agent_plugins[agent_id]
                logger.info(f"Cleaned up agent plugin: {agent_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up agent plugin: {str(e)}", exc_info=True)