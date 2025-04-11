
import logging
import httpx
import json
import yaml
import asyncio
from collections import deque
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from semantic_kernel.functions import KernelArguments, kernel_function
from semantic_kernel.connectors.openapi_plugin.openapi_function_execution_parameters import OpenAPIFunctionExecutionParameters
from semantic_kernel.core_plugins.sessions_python_tool.sessions_python_plugin import SessionsPythonTool
from semantic_kernel.filters import FunctionInvocationContext
from opentelemetry import trace
from app.models import Agent, Tool, Authentication
from app.config import get_settings

# Get a tracer
tracer = trace.get_tracer(__name__)


# Create a thread-safe shared queue for capturing function calls
# Use module-level dictionary to track function calls per session
function_call_queues = {}

class KernelFactory:
    @staticmethod
    async def create_kernel(agent: Agent, session_id: str = None) -> Kernel:
        with tracer.start_as_current_span("create_kernel") as span:
            span.set_attribute("agent_id", agent.id)
            span.set_attribute("provider", agent.modelSelection.provider)
            span.set_attribute("model", agent.modelSelection.model)
            
            kernel = Kernel()

            # If session_id provided, create a queue for this session
            if session_id:
                function_call_queues[session_id] = deque()

            # Define the auto function invocation filter that will be used by the kernel
            async def function_invocation_filter(context: FunctionInvocationContext, next):
                """A filter that will be called for each function call in the response."""
                function_name = context.function.name
                
                # if "messages" not in context.arguments:
                #     await next(context)
                #     return
                    
                # Log function call
                #print(f"Agent [{function_name}] called with messages: {context.arguments['messages']}")
                
                # Add to queue if we have a session_id
                if session_id and session_id in function_call_queues:
                    function_call_queues[session_id].append({
                        "type": "function_start",
                        "function": function_name,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                
                # Execute the function
                await next(context)
                
                # Log function result
                print(f"Response from agent [{function_name}]: {context.result.value}")
                
                # Add result to queue if we have a session_id
                if session_id and session_id in function_call_queues:
                    function_call_queues[session_id].append({
                        "type": "function_end",
                        "function": function_name,
                        "timestamp": asyncio.get_event_loop().time()
                    })

            if agent.displayFunctionCallStatus:       
                kernel.add_filter("function_invocation", function_invocation_filter)

            settings = get_settings()

            if agent.agentType == "ChatCompletionAgent":
                with tracer.start_as_current_span("configure_chat_completion_agent"):

                    if agent.modelSelection.provider == "AzureOpenAI":
                        with tracer.start_as_current_span("configure_azure_openai"):
                            chat_service = AzureChatCompletion(
                                deployment_name=agent.modelSelection.model,
                                endpoint=settings.azure_openai_endpoint,
                                api_key=settings.azure_openai_api_key,
                                service_id=agent.id
                                
                            )
                            kernel.add_service(chat_service)
                    
                    elif agent.modelSelection.provider == "AzureAIInference":
                        with tracer.start_as_current_span("configure_azure_ai_inference"):
                            chat_service = AzureAIInferenceChatCompletion(
                                ai_model_id=agent.modelSelection.model,
                                endpoint=settings.azure_ai_endpoint,
                                api_key=settings.azure_ai_api_key,
                                service_id=agent.id
                            )
                            kernel.add_service(chat_service)
            elif agent.agentType == "AzureAIAgent":
                with tracer.start_as_current_span("configure_azure_ai_agent"):
                    pass

            # Configure tools based on agent configuration
            if agent.tools:
                with tracer.start_as_current_span("configure_tools") as tools_span:
                    tools_span.set_attribute("tool_count", len(agent.tools))
                    for tool in agent.tools:
                        
                        # Register appropriate plugins based on tool.id
                        with tracer.start_as_current_span(f"register_tool_{tool.id}") as tool_span:
                            tool_span.set_attribute("tool.id", tool.id)
                            
                            # Determine tool type and handle accordingly
                            tool_type = tool.type
                            tool_span.set_attribute("tool.type", tool_type)
                            
                            if tool_type == "OpenAPI":
                                await KernelFactory._register_openapi_tool(kernel, tool, tool_span)
                            else:
                                tool_span.set_attribute("tool.error", f"Unsupported tool type: {tool_type}")
                                logging.warning(f"Unsupported tool type: {tool_type}")
                                pass
                    
            return kernel
    
    @staticmethod
    async def _fetch_openapi_spec(url: str, authentications: list = None) -> dict:
        """Fetch and parse an OpenAPI specification from a URL.
        
        Args:
            url: The URL to fetch the OpenAPI spec from
            authentications: Optional list of authentication objects in the format
                            [{"type": "Header", "headerName": "name", "headerValue": "value"}]
        
        Returns:
            The parsed OpenAPI specification as a dictionary
        """
        headers = {}
        
        # Add authentication headers if provided
        if authentications:
            for auth in authentications:
                if auth.type == "Header":
                    headers[auth.headerName] = auth.headerValue
    
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # Try to parse as JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                # If not JSON, try as YAML
                return yaml.safe_load(response.text)
    
    @staticmethod
    async def _register_openapi_tool(kernel: Kernel, tool: Tool, span: trace.Span) -> None:
        """Register an OpenAPI tool with the kernel."""
        span.set_attribute("tool.type", "OpenAPI")
        span.set_attribute("tool.id", tool.id)
        span.set_attribute("tool.name", tool.name)
        
        # Create authentication callback
        auth_callback = None
        if tool.authentications:
            auth_callbacks = []
            for auth in tool.authentications:
                if auth.type == "Header":
                    # Create a closure for header authentication
                    header_name = auth.headerName
                    header_value = auth.headerValue
                    
                    # Define the callback with the correct signature
                    def auth_callback_header(**kwargs):
                        # This function receives headers as kwargs, not a request object
                        headers = kwargs.get("headers", {})
                        headers[header_name] = header_value
                        return headers
                
                    auth_callbacks.append(auth_callback_header)
                    span.set_attribute("tool.auth.type", "Header")
                    span.set_attribute("tool.auth.header_name", auth.headerName)

                    span.set_attribute("tool.auth.type", "Header")
                    span.set_attribute("tool.auth.header_name", auth.headerName)
            
            # Combine multiple auth callbacks if needed
            if len(auth_callbacks) == 1:
                auth_callback = auth_callbacks[0]
            elif len(auth_callbacks) > 1:
                def combined_auth_callback(**kwargs):
                    headers = kwargs.get("headers", {})
                    for callback in auth_callbacks:
                        headers = callback(headers=headers)
                    return headers
                auth_callback = combined_auth_callback
        
        # Get OpenAPI spec
        if tool.specUrl:
            span.set_attribute("tool.spec_source", "url")
            span.set_attribute("tool.spec_url", tool.specUrl)
            logging.info(f"Fetching OpenAPI spec from URL: {tool.specUrl}")
            try:
                # Pass any authentication details to the fetch method
                parsed_spec = await KernelFactory._fetch_openapi_spec(
                    tool.specUrl, 
                    authentications=tool.authentications
                )
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("tool.error", str(e))
                span.set_attribute("tool.fetch_spec", "failed")
                span.set_attribute("tool.spec_source", "url")
                span.set_attribute("tool.spec_url", tool.specUrl)
                logging.error(f"Failed to fetch OpenAPI spec: {tool.specUrl} {str(e)}")
                raise Exception(f"Failed to fetch OpenAPI spec {tool.specUrl} {str(e)}")
                return
        else:
            span.set_attribute("tool.error", "No spec or specUrl provided")
            logging.error(f"OpenAPI tool has no spec or specUrl")
            return
        
        # Register the OpenAPI plugin
        try:
            plugin_name = tool.name.replace(" ", "")
            kernel.add_plugin_from_openapi(
                plugin_name=plugin_name,
                openapi_parsed_spec=parsed_spec,
                execution_settings=OpenAPIFunctionExecutionParameters(
                    auth_callback=auth_callback,
                    enable_payload_namespacing=True,
                    # Don't allow delete operations to be safe for now
                    operation_selection_predicate=lambda op: op.method.lower() in ["get", "post", "put"],
                )
            )
            span.set_attribute("tool.registration", "success")
            logging.info(f"Registered OpenAPI tool: {tool.name} with ID: {tool.id}")
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("tool.registration", "failed")
            span.set_attribute("tool.error", str(e))
            logging.error(f"Failed to register OpenAPI tool: {str(e)}")
