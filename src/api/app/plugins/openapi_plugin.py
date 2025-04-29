# app/plugins/openapi_plugin.py
import json
import logging
import httpx
import yaml
from typing import Dict, List, Any, Optional, Callable
from opentelemetry import trace
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

from semantic_kernel.functions.kernel_plugin import KernelPlugin
from semantic_kernel.connectors.openapi_plugin.openapi_function_execution_parameters import OpenAPIFunctionExecutionParameters
from app.models import Tool, Authentication
from app.plugins.base import PluginBase
from app.services.openapi_spec_cache import OpenAPISpecCache

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class OpenAPIPluginHandler(PluginBase):
    """Handles OpenAPI plugins for AI Agents."""
    
    def __init__(self):
        """Initialize the OpenAPI plugin handler."""
        self._plugins = {}  # Track created plugins for cleanup
        self._spec_cache = OpenAPISpecCache.get_instance()
    
    async def initialize(self, tool: Tool) -> Any:
        """Initialize an OpenAPI plugin from tool configuration."""
        if tool.type != "OpenAPI":
            return None
            
        with tracer.start_as_current_span("initialize_openapi_plugin") as span:
            span.set_attribute("tool_id", tool.id)
            span.set_attribute("tool_name", tool.name)
            
            try:
                # Extract API specification URL
                spec_url = tool.specUrl
                if not spec_url:
                    logger.error(f"Missing specUrl for OpenAPI tool: {tool.id}")
                    span.set_attribute("error", "missing_spec_url")
                    return None
                
                span.set_attribute("spec_url", spec_url)
                
                # Handle authentication configuration
                auth_callback = None
                if tool.authentications:
                    auth_callback = self._create_auth_callback(tool.authentications)
                
                # Use the spec cache to fetch the spec
                parsed_spec = await self._spec_cache.get_spec(spec_url, tool.authentications)
                if not parsed_spec:
                    logger.error(f"Failed to fetch or parse OpenAPI spec: {spec_url}")
                    return None
                
                # Create OpenAPI execution parameters
                execution_params = OpenAPIFunctionExecutionParameters(
                    auth_callback=auth_callback,
                    enable_dynamic_payload=True,
                    enable_payload_namespacing=True,
                    # Restrict to safer operations
                    operation_selection_predicate=lambda op: op.method.lower() in ["get", "post", "put"]
                )
                
                # Create the plugin
                plugin_name = tool.name.replace(" ", "")
                kernel_plugin = KernelPlugin.from_openapi(
                    plugin_name=plugin_name,
                    openapi_parsed_spec=parsed_spec,
                    execution_settings=execution_params
                )
                
                # Store for cleanup
                self._plugins[tool.id] = {
                    "plugin": kernel_plugin,
                    "name": plugin_name
                }
                
                logger.info(f"Successfully initialized OpenAPI plugin: {tool.name}")
                return kernel_plugin
                
            except Exception as e:
                logger.error(f"Failed to initialize OpenAPI plugin: {str(e)}", exc_info=True)
                span.record_exception(e)
                return None
    
    async def get_kernel_plugin(self, plugin: Any) -> Optional[KernelPlugin]:
        """Return the plugin for Semantic Kernel."""
        # The plugin is already a KernelPlugin, so return it directly
        return plugin
    
    async def cleanup(self, plugin: Any) -> None:
        """Clean up resources used by the plugin."""
        # Find and remove from tracking
        plugin_id = None
        for pid, info in self._plugins.items():
            if info["plugin"] == plugin:
                plugin_id = pid
                break
                
        if plugin_id:
            del self._plugins[plugin_id]
    
    def _create_auth_callback(self, authentications: List[Authentication]) -> Optional[Callable]:
        """Create authentication callback function for OpenAPI requests."""
        if not authentications:
            return None
        
        auth_callbacks = []
        
        for auth in authentications:
            if auth.type == "Header":
                header_name = auth.headerName
                header_value = auth.headerValue
                
                if header_name and header_value:
                    # Create a closure for header authentication
                    def header_auth_callback(name=header_name, value=header_value, **kwargs):
                        headers = kwargs.get("headers", {})
                        headers[name] = value
                        return headers
                    
                    auth_callbacks.append(header_auth_callback)
        
            # if auth.type == "EntraID-AppIdentity":
            #     # You may want to allow specifying a resource/audience in the Authentication model
            #     resource = getattr(auth, "resource", "https://management.azure.com/.default")
            #     async def entra_id_auth_callback(**kwargs):
            #         credential = DefaultAzureCredential()
            #         token = await credential.get_token(resource)
            #         headers = kwargs.get("headers", {})
            #         headers["Authorization"] = f"Bearer {token.token}"
            #         await credential.close()
            #         return headers
            #     auth_callbacks.append(entra_id_auth_callback)
        # No auth callbacks created
        if not auth_callbacks:
            return None
        
        # Create combined auth callback if multiple methods
        if len(auth_callbacks) == 1:
            return auth_callbacks[0]
        else:
            # Combine multiple callbacks
            def combined_auth_callback(**kwargs):
                headers = kwargs.get("headers", {})
                for callback in auth_callbacks:
                    headers = callback(headers=headers, **kwargs)
                return headers
            
            return combined_auth_callback