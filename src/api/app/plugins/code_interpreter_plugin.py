# app/plugins/code_interpreter_plugin.py
import logging
from typing import Any, Dict, List, Optional
import asyncio
from datetime import datetime, timezone
from opentelemetry import trace
from azure.identity.aio import DefaultAzureCredential

from semantic_kernel.core_plugins.sessions_python_tool import SessionsPythonTool
from semantic_kernel.exceptions.function_exceptions import FunctionExecutionException

from app.models import Tool
from app.plugins.base import PluginBase
from app.config.config import get_settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class CodeInterpreterPluginHandler(PluginBase):
    """Handles code interpreter functionality using SessionsPythonTool."""
    
    def __init__(self):
        """Initialize the code interpreter plugin handler."""
        self._sessions_tools = {}  # Track created sessions tools for cleanup
        self._auth_tokens = {}  # Cache auth tokens per agent
    
    async def initialize(self, tool: Tool, agent_id: str = None, **kwargs) -> Any:
        """Initialize a code interpreter plugin from tool configuration."""
        if tool.type != "CodeInterpreter":
            return None
            
        with tracer.start_as_current_span("initialize_code_interpreter_plugin") as span:
            span.set_attribute("tool_id", tool.id)
            span.set_attribute("tool_name", tool.name)
            span.set_attribute("agent_id", agent_id or "unknown")
            
            try:
                # Check if Azure Container Apps session pool is configured
                settings = get_settings()
                if not settings.aca_pool_management_endpoint:
                    error_msg = (
                        "Code interpreter requires Azure Container Apps session pool to be configured. "
                        "Please set the ACA_POOL_MANAGEMENT_ENDPOINT environment variable with your "
                        "Azure Container Apps session pool endpoint."
                    )
                    logger.warning(error_msg)
                    # For now, we'll return None to indicate the plugin couldn't be initialized
                    # In production, you might want to raise an exception or provide a fallback
                    return None
                
                # Create unique key for this agent's session
                session_key = f"{agent_id}_{tool.id}" if agent_id else tool.id
                
                # Create auth callback for this specific session
                auth_callback = self._create_auth_callback(session_key)
                
                # Create the sessions Python tool
                sessions_tool = SessionsPythonTool(
                    auth_callback=auth_callback
                )
                
                # Store the tool for cleanup
                self._sessions_tools[session_key] = sessions_tool
                
                logger.info(f"Initialized code interpreter for agent {agent_id} with tool {tool.id}")
                span.set_attribute("session_key", session_key)
                
                return {
                    "session_key": session_key,
                    "sessions_tool": sessions_tool,
                    "tool_config": tool
                }
                
            except Exception as e:
                error_msg = f"Failed to initialize code interpreter for tool '{tool.name}': {str(e)}"
                logger.error(error_msg, exc_info=True)
                span.set_attribute("error", error_msg)
                raise
    
    async def get_kernel_plugin(self, plugin_data: Any) -> Any:
        """Return the plugin in a format suitable for Semantic Kernel."""
        if not plugin_data or not isinstance(plugin_data, dict):
            return None
            
        sessions_tool = plugin_data.get("sessions_tool")
        if not sessions_tool:
            return None
            
        # The SessionsPythonTool itself is the kernel plugin
        return sessions_tool
    
    async def cleanup(self, plugin_data: Any) -> None:
        """Clean up resources used by the plugin."""
        if not plugin_data or not isinstance(plugin_data, dict):
            return
            
        session_key = plugin_data.get("session_key")
        if session_key:
            # Remove from our tracking
            self._sessions_tools.pop(session_key, None)
            self._auth_tokens.pop(session_key, None)
            
            logger.info(f"Cleaned up code interpreter session: {session_key}")
    
    def _create_auth_callback(self, session_key: str):
        """Create an authentication callback for the sessions tool."""
        
        async def auth_callback() -> str:
            """Auth callback for the SessionsPythonTool.
            This uses Azure's DefaultAzureCredential to get an access token.
            """
            try:
                # Check if we have a cached token that's still valid
                current_utc_timestamp = int(datetime.now(timezone.utc).timestamp())
                cached_token = self._auth_tokens.get(session_key)
                
                if cached_token and cached_token.expires_on > current_utc_timestamp:
                    return cached_token.token
                
                # Get new token
                credential = DefaultAzureCredential()
                settings = get_settings()
                
                # Use the Azure Container Apps session pool scope
                token_scope = "https://dynamicsessions.io/.default"
                
                auth_token = await credential.get_token(token_scope)
                
                # Cache the token
                self._auth_tokens[session_key] = auth_token
                
                logger.debug(f"Retrieved new auth token for session {session_key}")
                return auth_token.token
                
            except Exception as e:
                error_msg = f"Failed to retrieve auth token for code interpreter session {session_key}: {str(e)}"
                logger.error(error_msg)
                raise FunctionExecutionException(error_msg) from e
        
        return auth_callback
