# app/plugins/mcp_plugin.py
import json
import logging
import os
import platform
import shutil
import subprocess
from typing import Dict, Any, Optional, List
from opentelemetry import trace

from semantic_kernel.connectors.mcp import MCPStdioPlugin, MCPSsePlugin
from app.models import Tool
from app.plugins.base import PluginBase
from app.config.config import get_settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class MCPPluginHandler(PluginBase):
    """Handles MCP plugins specifically."""
    
    def __init__(self):
        """Initialize the MCP plugin handler."""
        self._plugins = {}  # Track created plugins for cleanup
        self.settings = get_settings()
    
    async def initialize(self, tool: Tool, agent_id=None, **kwargs) -> Any:
        """Initialize an MCP plugin from tool configuration."""
        with tracer.start_as_current_span("initialize_mcp_plugin") as span:
            span.set_attribute("tool_id", tool.id)
            span.set_attribute("tool_name", tool.name)
            if agent_id:
                span.set_attribute("agent_id", agent_id)
            
            # Check if MCP plugins are enabled in settings
            if not self.settings.mcp_enable_plugins:
                logger.info("MCP plugins are disabled in settings")
                return None
                
            if not tool.mcpDefinition:
                logger.warning(f"No MCP definition found for tool: {tool.id}")
                return None
                
            try:                # Parse MCP definition
                if isinstance(tool.mcpDefinition, str):
                    config = json.loads(tool.mcpDefinition)
                else:
                    config = tool.mcpDefinition
                
                # Handle the standard mcpServers format used in agent tools
                if "mcpServers" in config:
                    # Extract first server from config for now
                    server_name = list(config["mcpServers"].keys())[0]
                    server_config = config["mcpServers"][server_name]
                    
                    plugin_name = server_name
                    description = f"MCP plugin for {server_name}"
                    
                    # Extract environment variables if present
                    env_vars = server_config.get("env")
                    
                    # Check if this is a remote MCP server
                    if server_config.get("type") == "remote":
                        plugin = self._create_remote_mcp_plugin(server_config, plugin_name, description)
                        logger.info(f"Creating remote MCP plugin for '{plugin_name}'")
                    else:
                        # Default to local MCP plugin
                        command = server_config.get("command")
                        args = server_config.get("args", []) 
                        plugin = self._create_local_mcp_plugin(command, args, plugin_name, description, env_vars)
                        logger.info(f"Creating local MCP plugin for '{plugin_name}' with command: {command} {' '.join(args)}")                
                else:
                    # Fallback to direct config access
                    plugin_name = tool.name
                    description = config.get("description", f"MCP plugin for {tool.name}")
                    
                    # Extract environment variables if present
                    env_vars = config.get("env")
                      # Process direct config (should be indented inside the else block)
                    if config.get("type") == "remote":
                        plugin = self._create_remote_mcp_plugin(config, plugin_name, description)
                        logger.info(f"Creating remote MCP plugin for '{plugin_name}'")
                    else:
                        command = config.get("command")
                        args = config.get("args", [])
                        plugin = self._create_local_mcp_plugin(command, args, plugin_name, description, env_vars)
                        logger.info(f"Creating local MCP plugin for '{plugin_name}' with command: {command} {' '.join(args)}")
                
                # Connect to the MCP server
                logger.info(f"Connecting to MCP server for tool: {tool.id}{' in agent: ' + agent_id if agent_id else ''}")
                await plugin.connect()
                logger.info(f"Successfully connected to MCP server for tool: {tool.id}{' in agent: ' + agent_id if agent_id else ''}")
                
                # Store for cleanup with compound key
                plugin_key = f"{agent_id}:{tool.id}" if agent_id else tool.id
                logger.debug(f"Storing MCP plugin with key: {plugin_key}")
                self._plugins[plugin_key] = plugin
                return plugin
                
            except Exception as e:
                logger.error(f"Failed to initialize MCP plugin for tool {tool.id}: {str(e)}", exc_info=True)
                span.record_exception(e)
                return None
    
    def _create_local_mcp_plugin(self, command: str, args: List[str], 
                                 name: str, description: str, env: Optional[Dict[str, str]] = None) -> MCPStdioPlugin:
        """Create a local MCP plugin that runs on the server."""
        if not command:
            raise ValueError(f"Missing command for MCP plugin: {name}")
        
        # Handle npx command path on Windows
        if command == "npx" and platform.system() == "Windows":
            npx_path = self._find_npx_path()
            if npx_path:
                command = npx_path
                logger.info(f"Using npx from path: {npx_path}")
        
        # Log environment variables if provided
        if env:
            logger.info(f"Setting environment variables for MCP plugin '{name}': {list(env.keys())}")
            logger.debug(f"Environment variables for '{name}': {env}")
        
        # Create the plugin instance with longer timeouts
        return MCPStdioPlugin(
            name=name,
            description=description,
            command=command,
            args=args,
            env=env,
            connection_timeout=self.settings.mcp_timeout_seconds
        )
    
    def _create_remote_mcp_plugin(self, config: Dict[str, Any], 
                                 name: str, description: str) -> MCPSsePlugin:
        """Create a remote MCP plugin that connects to a remote endpoint."""
        endpoint = config.get("endpoint")
        if not endpoint:
            raise ValueError(f"Missing endpoint for remote MCP plugin: {name}")
        
        headers = {}
        
        # Handle authentication if provided
        if "auth" in config:
            auth_config = config["auth"]
            
            # API key authentication
            if "apiKey" in auth_config:
                header_name = auth_config.get("headerName", "Authorization")
                header_value = auth_config["apiKey"]
                prefix = auth_config.get("prefix", "Bearer")
                
                headers[header_name] = f"{prefix} {header_value}" if prefix else header_value
            
            # Basic header authentication
            elif "headers" in auth_config:
                headers.update(auth_config["headers"])
        
        # Create the remote MCP plugin
        return MCPSsePlugin(
            name=name,
            description=description,
            endpoint=endpoint,
            headers=headers,
            connection_timeout=self.settings.mcp_timeout_seconds
        )
    
    def _find_npx_path(self) -> Optional[str]:
        """Find npx executable path on the system."""
        # Try shutil.which first
        npx_path = shutil.which("npx")
        if npx_path:
            return npx_path
            
        # Check common locations on Windows
        if platform.system() == "Windows":
            common_paths = [
                os.path.join(os.environ.get("ProgramFiles", ""), "nodejs", "npx.cmd"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "npx.cmd"),
                "C:\\Program Files\\nodejs\\npx.cmd"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return path
                    
        return "npx"  # Fall back to letting the system resolve it
    
    async def get_kernel_plugin(self, plugin: Any) -> Any:
        """Return the MCP plugin for Semantic Kernel."""
        return plugin
    
    async def cleanup(self, plugin: Any) -> None:
        """Close the MCP plugin connection."""
        if not plugin:
            return
            
        try:
            # Find and remove from tracking using value lookup
            plugin_key = None
            for key, p in self._plugins.items():
                if p == plugin:
                    plugin_key = key
                    break
                    
            if plugin_key:
                # Extract agent info for logging
                agent_info = ""
                if ":" in plugin_key:
                    agent_id = plugin_key.split(":", 1)[0]
                    agent_info = f" for agent {agent_id}"
                    del self._plugins[plugin_key]
                
                # Clean up plugin resources
                if hasattr(plugin, 'close'):
                    await plugin.close()
                    logger.info(f"Cleaned up MCP plugin{agent_info}")
            
        except Exception as e:
            logger.error(f"Error cleaning up MCP plugin: {str(e)}", exc_info=True)