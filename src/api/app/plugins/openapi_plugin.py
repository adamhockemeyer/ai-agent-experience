import json
import logging
import httpx
import yaml
from typing import Dict, List, Any, Optional, Callable
from opentelemetry import trace

from semantic_kernel.functions.kernel_plugin import KernelPlugin
from semantic_kernel.connectors.openapi_plugin.openapi_function_execution_parameters import OpenAPIFunctionExecutionParameters
from app.plugins.plugin_manager import AgentPlugin

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class OpenAPIPlugin(AgentPlugin):
    """OpenAPI plugin implementation for AI Agents following Azure best practices."""
    
    def __init__(self):
        """Initialize the OpenAPI plugin."""
        self._plugin_name = "OpenAPI Plugin"
        self._kernel_plugin = None
        self._config = None
    
    @property
    def name(self) -> str:
        """Get the name of the plugin."""
        return self._plugin_name
    
    async def initialize(self, **kwargs) -> bool:
        """Initialize the OpenAPI plugin with the given configuration following Azure best practices.
        
        Args:
            config (Dict[str, Any]): Plugin configuration with either 'openApiUrl' or 'openApiSpec' and 'apiKey' (optional)
            session_id (str, optional): Session identifier for tracking
            
        Returns:
            bool: True if initialization was successful
        """
        with tracer.start_as_current_span("initialize_openapi_plugin") as span:
            config = kwargs.get("config", {})
            session_id = kwargs.get("session_id")
            
            span.set_attribute("session_id", session_id or "unknown")
            
            # Parse config if it's a string
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                    span.set_attribute("config_format", "json_string")
                except json.JSONDecodeError:
                    logger.error("Invalid JSON configuration for OpenAPI plugin")
                    span.set_attribute("error", "invalid_json_config")
                    return False
            
            self._config = config
            span.set_attribute("plugin_type", "openapi")
            
            # Extract plugin name if provided
            if "name" in config:
                self._plugin_name = config["name"]
                span.set_attribute("plugin_name", self._plugin_name)
            
            # Extract API specification
            spec_url = config.get("openApiUrl")
            spec_content = config.get("openApiSpec")
            api_key = config.get("apiKey")
            
            # Handle authentication configuration
            authentications = config.get("authentications", [])
            
            try:
                # Fetch OpenAPI spec if URL provided
                if spec_url:
                    span.set_attribute("spec_source", "url")
                    span.set_attribute("spec_url", spec_url)
                    logger.info(f"Fetching OpenAPI spec from URL: {spec_url}")
                    
                    parsed_spec = await self._fetch_openapi_spec(spec_url, authentications)
                    
                    # Extract name from URL if not specified
                    if "name" not in config:
                        self._plugin_name = spec_url.split("/")[-1].split(".")[0]
                
                # Use provided spec content
                elif spec_content:
                    span.set_attribute("spec_source", "content")
                    logger.info("Using provided OpenAPI spec content")
                    
                    # Handle different formats of spec_content
                    if isinstance(spec_content, str):
                        try:
                            parsed_spec = json.loads(spec_content)
                        except json.JSONDecodeError:
                            try:
                                parsed_spec = yaml.safe_load(spec_content)
                            except yaml.YAMLError:
                                logger.error("Failed to parse OpenAPI spec content")
                                span.set_attribute("error", "invalid_spec_content")
                                return False
                    else:
                        parsed_spec = spec_content
                    
                    # Extract name from spec content
                    if "name" not in config and isinstance(parsed_spec, dict) and "info" in parsed_spec:
                        self._plugin_name = parsed_spec["info"].get("title", "OpenAPI Plugin")
                
                # No spec provided
                else:
                    logger.warning("OpenAPI plugin requires either URL or spec content")
                    span.set_attribute("error", "missing_spec")
                    return False
                
                # Create auth callback if needed
                auth_callback = self._create_auth_callback(authentications, api_key)
                
                # Create OpenAPI execution parameters
                execution_params = OpenAPIFunctionExecutionParameters(
                    auth_callback=auth_callback,
                    enable_dynamic_payload=True,
                    enable_payload_namespacing=True,
                    # Follow Azure best practices - restrict to safer operations
                    operation_selection_predicate=lambda op: op.method.lower() in ["get", "post", "put"]
                )
                
                # Create the actual plugin
                plugin_name = self._plugin_name.replace(" ", "")
                self._kernel_plugin = KernelPlugin.from_openapi(
                    plugin_name=plugin_name,
                    openapi_parsed_spec=parsed_spec,
                    execution_parameters=execution_params
                )
                
                logger.info(f"Successfully initialized OpenAPI plugin: {self._plugin_name}")
                span.set_attribute("initialization", "success")
                return True
                
            except Exception as e:
                logger.error(f"Failed to initialize OpenAPI plugin: {str(e)}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False
    
    async def close(self) -> None:
        """Clean up the OpenAPI plugin."""
        # Most OpenAPI plugins don't need special cleanup
        # Just release references to allow garbage collection
        self._kernel_plugin = None
    
    def to_kernel_plugin(self) -> Optional[KernelPlugin]:
        """Convert the plugin to a format that can be added to an agent."""
        return self._kernel_plugin
    
    async def _fetch_openapi_spec(self, url: str, authentications: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch and parse an OpenAPI specification from a URL following Azure best practices.
        
        Args:
            url: The URL to fetch the OpenAPI spec from
            authentications: Optional list of authentication objects
        
        Returns:
            The parsed OpenAPI specification as a dictionary
            
        Raises:
            Exception: If the fetch or parsing fails
        """
        with tracer.start_as_current_span("fetch_openapi_spec") as span:
            span.set_attribute("url", url)
            
            headers = {}
            
            # Add authentication headers if provided
            if authentications:
                for auth in authentications:
                    auth_type = auth.get("type")
                    
                    if auth_type == "Header" or auth_type == "header":
                        header_name = auth.get("headerName") or auth.get("name")
                        header_value = auth.get("headerValue") or auth.get("value")
                        
                        if header_name and header_value:
                            headers[header_name] = header_value
                            # Don't log actual values in telemetry for security
                            span.set_attribute(f"auth_header.{header_name}", "[REDACTED]")
                    
                    elif auth_type == "BearerToken" or auth_type == "bearer":
                        token = auth.get("token")
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                            span.set_attribute("auth_type", "bearer")
            
            # Azure best practice: Use async HTTP client with timeout and proper error handling
            try:
                timeout = httpx.Timeout(30.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    
                    # Try to parse as JSON first
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        # If not JSON, try as YAML
                        return yaml.safe_load(response.text)
                    
            except httpx.HTTPStatusError as e:
                # HTTP error like 404, 500, etc.
                logger.error(f"HTTP error fetching OpenAPI spec: {e.response.status_code} {str(e)}")
                span.set_attribute("error", f"http_status_{e.response.status_code}")
                raise Exception(f"Failed to fetch OpenAPI spec: HTTP {e.response.status_code}")
                
            except httpx.RequestError as e:
                # Network-related error
                logger.error(f"Network error fetching OpenAPI spec: {str(e)}")
                span.set_attribute("error", "network_error")
                raise Exception(f"Network error fetching OpenAPI spec: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error parsing OpenAPI spec: {str(e)}")
                span.set_attribute("error", "parse_error")
                raise Exception(f"Error parsing OpenAPI spec: {str(e)}")
    
    def _create_auth_callback(self, authentications: List[Dict[str, Any]], api_key: Optional[str] = None) -> Optional[Callable]:
        """Create authentication callback function for OpenAPI requests.
        
        Args:
            authentications: List of authentication configurations
            api_key: Optional API key
            
        Returns:
            A callback function for authenticating requests or None if no auth needed
        """
        # If no authentications or API key, no callback needed
        if not authentications and not api_key:
            return None
        
        auth_callbacks = []
        
        # Process API key if provided
        if api_key:
            def api_key_callback(**kwargs):
                headers = kwargs.get("headers", {})
                # Default to x-api-key but this can be configured differently
                headers["x-api-key"] = api_key
                return headers
            
            auth_callbacks.append(api_key_callback)
        
        # Process other authentication methods
        for auth in authentications:
            auth_type = auth.get("type")
            
            if auth_type == "Header" or auth_type == "header":
                header_name = auth.get("headerName") or auth.get("name")
                header_value = auth.get("headerValue") or auth.get("value")
                
                if header_name and header_value:
                    # Create a closure for header authentication
                    def header_auth_callback(name=header_name, value=header_value, **kwargs):
                        headers = kwargs.get("headers", {})
                        headers[name] = value
                        return headers
                    
                    auth_callbacks.append(header_auth_callback)
            
            elif auth_type == "BearerToken" or auth_type == "bearer":
                token = auth.get("token")
                if token:
                    def bearer_auth_callback(token_value=token, **kwargs):
                        headers = kwargs.get("headers", {})
                        headers["Authorization"] = f"Bearer {token_value}"
                        return headers
                    
                    auth_callbacks.append(bearer_auth_callback)
        
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