import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import uuid
from typing import Dict, List, Optional, Any
from opentelemetry import trace

from semantic_kernel.connectors.mcp import MCPStdioPlugin
from app.config.config import get_settings
from app.plugins.plugin_manager import AgentPlugin

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class MCPPlugin(AgentPlugin):
    """ModelContextProtocol (MCP) plugin implementation."""
    
    def __init__(self):
        """Initialize the MCP plugin."""
        self._plugin_name = "MCP Plugin"
        self._mcp_plugin = None
        self._config = None
        self._session_id = str(uuid.uuid4())
        self._child_processes = set()
        self.settings = get_settings()
    
    @property
    def name(self) -> str:
        """Get the name of the plugin."""
        return self._plugin_name
    
    async def initialize(self, **kwargs) -> bool:
        """Initialize the MCP plugin with the given configuration."""
        with tracer.start_as_current_span("initialize_mcp_plugin"):
            config = kwargs.get("config", {})
            self._session_id = kwargs.get("session_id", self._session_id)
            
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON configuration for MCP plugin")
                    return False
            
            self._config = config
            
            # Extract MCP server configuration
            if "mcpServers" in config:
                mcp_servers = config["mcpServers"]
                if not mcp_servers or not isinstance(mcp_servers, dict):
                    logger.warning("No valid MCP servers defined in configuration")
                    return False
                
                # For simplicity, use the first server defined
                server_name, server_config = next(iter(mcp_servers.items()))
                self._plugin_name = server_name
                
                command = server_config.get("command")
                args = server_config.get("args", [])
                description = server_config.get("description", f"MCP plugin for {server_name}")
                
                if not command:
                    logger.warning(f"Missing command for MCP plugin '{server_name}'")
                    return False
                
                # Handle npx command path on Windows
                if command == "npx" and platform.system() == "Windows":
                    npx_path = self._find_npx_path()
                    if npx_path:
                        command = npx_path
                        logger.info(f"Using npx from path: {npx_path}")
                
                # Special handling for Playwright
                is_playwright = "playwright" in " ".join(args).lower() or "playwright" in server_name.lower()
                if is_playwright:
                    args = self._prepare_playwright_args(args)
                
                # Create and connect the MCP plugin
                try:
                    logger.info(f"Initializing MCP plugin '{server_name}'")
                    
                    # Create the plugin instance
                    self._mcp_plugin = MCPStdioPlugin(
                        name=server_name,
                        description=description,
                        command=command,
                        args=args
                    )
                    
                    # Connect to the MCP server
                    logger.info(f"Connecting to {server_name} MCP server...")
                    await self._mcp_plugin.connect()
                    logger.info(f"Successfully connected to {server_name} MCP server")
                    
                    # Record process ID for cleanup if available
                    if hasattr(self._mcp_plugin, '_proc') and self._mcp_plugin._proc and self._mcp_plugin._proc.pid:
                        self._child_processes.add(self._mcp_plugin._proc.pid)
                    
                    return True
                except Exception as e:
                    logger.error(f"Failed to initialize MCP plugin '{server_name}': {str(e)}", exc_info=True)
                    return False
            else:
                logger.warning("No MCP servers defined in configuration")
                return False
    
    async def close(self) -> None:
        """Clean up the MCP plugin."""
        with tracer.start_as_current_span("close_mcp_plugin"):
            if self._mcp_plugin:
                try:
                    logger.info(f"Disconnecting MCP plugin: {self.name}")
                    await self._mcp_plugin.disconnect()
                    self._mcp_plugin = None
                except Exception as e:
                    logger.warning(f"Error disconnecting MCP plugin: {str(e)}")
            
            # Terminate any child processes
            await self._terminate_child_processes()
    
    def to_kernel_plugin(self) -> Any:
        """Convert the plugin to a format that can be added to a kernel or agent."""
        return self._mcp_plugin if self._mcp_plugin else None
    
    def _prepare_playwright_args(self, args: List[str]) -> List[str]:
        """Prepare Playwright arguments to ensure clean sessions."""
        modified_args = list(args)  # Create a copy
        
        # Add headless flag if not already present
        if not any("--headless" in arg for arg in modified_args):
            modified_args.append("--headless")
        
        # Create a unique user-data-dir to avoid conflicts between sessions
        temp_dir = os.environ.get("TEMP") or os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        user_data_dir = os.path.join(temp_dir, f"playwright-data-{self._session_id}")
        
        # Add user data directory if not already present
        if not any("--user-data-dir" in arg for arg in modified_args):
            modified_args.append(f"--user-data-dir={user_data_dir}")
        
        # Additional browser arguments for better cleanup
        browser_args = [
            "--disable-dev-shm-usage",  # Overcome limited /dev/shm in containers
            "--disable-gpu",            # Reduce resource usage
            "--no-sandbox"              # For containerized environments
        ]
        
        # Add browser arguments if not already present
        for arg in browser_args:
            if not any(arg in a for a in modified_args):
                modified_args.append(arg)
        
        return modified_args
    
    def _find_npx_path(self) -> str:
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
    
    async def _terminate_child_processes(self) -> None:
        """Terminate any child processes started by this plugin."""
        for pid in self._child_processes:
            try:
                # Windows uses a different mechanism
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid), "/T"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    # Unix-like systems
                    os.kill(pid, 9)  # SIGKILL
                
                logger.info(f"Terminated process: {pid}")
            except Exception as e:
                logger.warning(f"Error terminating process {pid}: {str(e)}")
        
        # Also look for any stray Playwright browser processes
        await self._terminate_stray_browsers()
    
    async def _terminate_stray_browsers(self) -> None:
        """Terminate any stray browser processes started by Playwright."""
        try:
            # Browser process patterns to look for - specifically for Playwright
            # On Windows, use taskkill for chrome processes related to Playwright
            if platform.system() == "Windows":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/FI", "WINDOWTITLE eq *playwright*", "/T"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    subprocess.run(
                        ["taskkill", "/F", "/FI", 
                         f"IMAGENAME eq chrome.exe", "/FI", 
                         f"WINDOWTITLE eq *playwright*", "/T"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception as e:
                    logger.warning(f"Error running taskkill: {str(e)}")
            else:
                # On Unix systems, use pkill
                try:
                    subprocess.run(
                        ["pkill", "-f", "playwright.*chrome"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception as e:
                    logger.warning(f"Error running pkill: {str(e)}")
            
            logger.info("Cleaned up any stray browser processes")
        except Exception as e:
            logger.warning(f"Error in browser cleanup: {str(e)}")