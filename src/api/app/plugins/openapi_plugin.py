# app/plugins/openapi_plugin.py
import json
import logging
import httpx
import yaml
import re
from typing import Dict, List, Any, Optional, Callable
from opentelemetry import trace
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

from semantic_kernel.functions.kernel_plugin import KernelPlugin
from semantic_kernel.connectors.openapi_plugin.openapi_function_execution_parameters import OpenAPIFunctionExecutionParameters
from semantic_kernel.exceptions.function_exceptions import FunctionInitializationError
from pydantic.errors import PydanticUserError
from pydantic_core._pydantic_core import ValidationError

from app.models import Tool, Authentication
from app.plugins.base import PluginBase
from app.services.openapi_spec_cache import OpenAPISpecCache

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class OpenAPIPluginError(Exception):
    """Exception raised for OpenAPI plugin errors that should be shown to users."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, 
                 tool_id: str = "", tool_name: str = "", spec_url: str = ""):
        self.message = message
        self.original_error = original_error
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.spec_url = spec_url
        super().__init__(self.message)

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
                    error_msg = f"Missing OpenAPI specification URL for tool '{tool.name}'"
                    logger.error(error_msg)
                    span.set_attribute("error", "missing_spec_url")
                    raise OpenAPIPluginError(error_msg, tool_id=tool.id, tool_name=tool.name)
                
                span.set_attribute("spec_url", spec_url)
                
                # Handle authentication configuration
                auth_callback = None
                if tool.authentications:
                    auth_callback = self._create_auth_callback(tool.authentications)
                
                # Use the spec cache to fetch the spec
                parsed_spec = await self._spec_cache.get_spec(spec_url, tool.authentications)
                if not parsed_spec:
                    error_msg = f"Failed to fetch or parse OpenAPI spec from {spec_url}. Verify the URL is accessible and returns valid OpenAPI JSON or YAML."
                    logger.error(error_msg)
                    raise OpenAPIPluginError(error_msg, tool_id=tool.id, tool_name=tool.name, spec_url=spec_url)
                
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
                try:
                    kernel_plugin = KernelPlugin.from_openapi(
                        plugin_name=plugin_name,
                        openapi_parsed_spec=parsed_spec,
                        execution_settings=execution_params
                    )
                except FunctionInitializationError as e:
                    # Extract useful information from the exception chain
                    error_msg = self._extract_user_friendly_error(e, tool.name)
                    logger.error(f"Failed to initialize OpenAPI plugin: {error_msg}", exc_info=True)
                    raise OpenAPIPluginError(error_msg, original_error=e, tool_id=tool.id, tool_name=tool.name, spec_url=spec_url)
                except Exception as e:
                    error_msg = f"Failed to initialize OpenAPI plugin '{tool.name}': {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    raise OpenAPIPluginError(error_msg, original_error=e, tool_id=tool.id, tool_name=tool.name, spec_url=spec_url)
                
                # Store for cleanup
                self._plugins[tool.id] = {
                    "plugin": kernel_plugin,
                    "name": plugin_name
                }
                
                logger.info(f"Successfully initialized OpenAPI plugin: {tool.name}")
                return kernel_plugin
                
            except OpenAPIPluginError:
                # Re-raise our custom errors
                raise
            except Exception as e:
                error_msg = f"Unexpected error initializing OpenAPI plugin '{tool.name}': {str(e)}"
                logger.error(error_msg, exc_info=True)
                span.record_exception(e)
                raise OpenAPIPluginError(error_msg, original_error=e, tool_id=tool.id, tool_name=tool.name, spec_url=tool.specUrl or "")
                
    def _extract_user_friendly_error(self, error: Exception, tool_name: str) -> str:
        """Extract a user-friendly error message from exception chain."""
        # Get the full error string to use in pattern matching
        full_error_str = str(error)
        
        # Check for specific function name pattern errors - handle both direct and nested
        if isinstance(error, FunctionInitializationError) or "KernelFunction failed to initialize" in full_error_str:
            # Check for the function name error pattern in the raw error message
            # This handles both ValidationError cases and when the error is re-wrapped
            function_name_match = re.search(r'function\s+([A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)', full_error_str)
            if function_name_match:
                invalid_function = function_name_match.group(1)
                # If we found a function name with a hyphen, that's likely our issue
                if '-' in invalid_function:
                    return (f"Function name '{invalid_function}' in OpenAPI spec contains invalid characters. "
                            f"Function names must only contain letters, numbers, and underscores (no hyphens). "
                            f"Please update your OpenAPI spec to use compliant operation IDs.")
            
            # Look for validation error patterns deeper in the exception chain
            cause = error.__cause__
            if cause:
                # Try to extract validation error details
                if isinstance(cause, ValidationError):
                    for error_item in cause.errors():
                        if error_item.get("type") == "string_pattern_mismatch" and error_item.get("loc") == ("name",):
                            invalid_name = error_item.get("input")
                            if invalid_name:
                                return (f"Function name '{invalid_name}' in OpenAPI spec contains invalid characters. " 
                                        f"Function names must only contain letters, numbers, and underscores. "
                                        f"Please update your OpenAPI spec to use compliant operation IDs.")
                
                # Also check the error message from the cause
                cause_str = str(cause)
                if "string_pattern_mismatch" in cause_str and "^[0-9A-Za-z_]+$" in cause_str:
                    # Try to extract the function name from the error message
                    name_match = re.search(r"input_value='([^']+)'", cause_str)
                    if name_match:
                        invalid_name = name_match.group(1)
                        return (f"Function name '{invalid_name}' in OpenAPI spec contains invalid characters. " 
                                f"Function names must only contain letters, numbers, and underscores. "
                                f"Please update your OpenAPI spec to use compliant operation IDs.")
            
            # If we found KernelFunction failed message but couldn't extract specifics
            if "KernelFunction failed to initialize: Failed to create KernelFunctionMetadata" in full_error_str:
                return (f"The OpenAPI plugin '{tool_name}' could not be initialized due to invalid function names. "
                       f"Function names in OpenAPI specs must only contain letters, numbers, and underscores. "
                       f"Please check your OpenAPI spec for operation IDs with hyphens or other special characters.")
                
        # Generic user-friendly message with original error
        return f"Error initializing OpenAPI plugin '{tool_name}': {full_error_str}"
    
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