import asyncio
import json
import logging
import os
import platform
import shutil
from typing import Dict, List, Optional, Any
from opentelemetry import trace

from semantic_kernel.connectors.mcp import MCPStdioPlugin
from app.config.config import get_settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class MCPPluginManager:
    """Manager for dynamically creating and managing MCP plugins based on agent configuration."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the plugin manager with optional configuration."""
        self.config = config or {}
        self.plugins = []
        self.warnings = []
        self.settings = get_settings()
    
    async def __aenter__(self):
        """Initialize all configured plugins when entering context."""
        if not self.config:
            logger.info("No MCP plugins configured")
            return self
            
        if not self.settings.mcp_enable_plugins:
            logger.info("MCP plugins are disabled in settings")
            return self
            
        await self._initialize_plugins()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up all plugins when exiting context."""
        for plugin in self.plugins:
            try:
                if hasattr(plugin, 'close'):
                    await plugin.close()
                logger.info(f"Cleaned up MCP plugin: {plugin.name}")
            except Exception as e:
                logger.warning(f"Error cleaning up MCP plugin: {str(e)}")
        
        self.plugins = []
    
    async def _initialize_plugins(self):
        """Initialize each plugin defined in the configuration."""
        for plugin_name, plugin_config in self.config.items():
            try:
                command = plugin_config.get("command")
                args = plugin_config.get("args", [])
                description = plugin_config.get("description", f"MCP plugin for {plugin_name}")
                
                if not command:
                    logger.warning(f"Missing command for MCP plugin '{plugin_name}'")
                    self.warnings.append(f"⚠️ Missing command for plugin '{plugin_name}'")
                    continue
                
                # Handle npx command path on Windows
                if command == "npx" and platform.system() == "Windows":
                    npx_path = self._find_npx_path()
                    if npx_path:
                        command = npx_path
                        logger.info(f"Using npx from path: {npx_path}")
                
                logger.info(f"Initializing MCP plugin '{plugin_name}'")
                
                # Create the plugin instance
                plugin = MCPStdioPlugin(
                    name=plugin_name,
                    description=description,
                    command=command,
                    args=args
                )
                
                # Connect to the MCP server
                logger.info(f"Connecting to {plugin_name} MCP server...")
                await plugin.connect()
                logger.info(f"Successfully connected to {plugin_name} MCP server")
                
                # Add to our list of active plugins
                self.plugins.append(plugin)
                
            except Exception as e:
                logger.error(f"Failed to initialize MCP plugin '{plugin_name}': {str(e)}", exc_info=True)
                self.warnings.append(f"⚠️ Failed to initialize plugin '{plugin_name}': {str(e)}")
    
    def _find_npx_path(self):
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


def create_mcp_config_from_json(json_str: str) -> Dict:
    """Parse MCP configuration from JSON string."""
    try:
        config = json.loads(json_str)
        # Handle the standard mcpServers format used in agent tools
        if "mcpServers" in config:
            return {
                name: {
                    "command": server_config.get("command"),
                    "args": server_config.get("args", []),
                    "description": f"MCP plugin for {name}"
                } 
                for name, server_config in config["mcpServers"].items()
            }
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for MCP configuration: {str(e)}")
        return {}