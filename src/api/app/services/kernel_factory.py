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
from semantic_kernel.filters import AutoFunctionInvocationContext, FilterTypes
from opentelemetry import trace
from app.models import Agent, Tool, Authentication
from app.config import get_settings
from app.services.function_call_stream import FunctionCallStream

# Get a tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class KernelFactory:
    @staticmethod
    async def create_kernel(agent: Agent, session_id: str = None) -> Kernel:
        """Create and configure a Semantic Kernel instance for the given agent.
        
        This method configures:
        1. The base kernel
        2. Function invocation filters (if needed)
        
        Note: AI services are configured in the AgentFactory, not here.
        Agent-specific plugins are handled by PluginManager.
        
        Args:
            agent: The agent configuration
            session_id: Optional session ID for tracking function calls
            
        Returns:
            A configured Kernel instance
        """
        with tracer.start_as_current_span("create_kernel") as span:
            span.set_attribute("agent_id", agent.id)
            
            kernel = Kernel()

            # Only add the filter if function call status should be displayed
            if agent.displayFunctionCallStatus and session_id:
                # Get or create a function call stream for this session
                function_stream = FunctionCallStream.get_or_create(session_id)
                
                async def auto_function_filter(context: AutoFunctionInvocationContext, next):
                    """A filter that will be called for auto-invoked functions."""
                    with tracer.start_as_current_span("auto_function_filter"):
                        function_name = context.function.name
                        plugin_name = context.function.plugin_name
                        
                        # Format arguments for logging/display
                        safe_args = {}
                        if context.arguments:
                            # Create a sanitized copy of arguments
                            for arg_name, arg_value in context.arguments.items():
                                if arg_name.lower() in ["key", "password", "secret", "token", "authorization"]:
                                    safe_args[arg_name] = "***REDACTED***"
                                elif isinstance(arg_value, str) and len(arg_value) > 100:
                                    safe_args[arg_name] = f"{arg_value[:97]}..."
                                else:
                                    safe_args[arg_name] = arg_value
                        
                        # Record start time for duration calculation
                        start_time = asyncio.get_event_loop().time()
                        
                        # Create function call info
                        call_info = {
                            "type": "function_start",
                            "function": function_name,
                            "plugin": plugin_name,
                            "arguments": safe_args,
                            "timestamp": start_time
                        }
                        
                        # Add to function call stream
                        function_stream.add_function_call(call_info)
                        
                        # Log the function call with more context
                        prefix = "[AUTO]"
                        logger.debug(f"{prefix} Function called: {plugin_name}.{function_name} with arguments: {safe_args}")
                        
                        # Execute the function
                        try:
                            await next(context)
                            
                            # Analyze the result to determine if it's actually an error
                            status = "success"
                            if hasattr(context, 'result') and context.result is not None:
                                # Try multiple ways to extract the result content
                                result_value = ""
                                if hasattr(context.result, 'value'):
                                    result_value = str(context.result.value)
                                elif hasattr(context.result, 'content'):
                                    result_value = str(context.result.content)
                                else:
                                    result_value = str(context.result)
                                
                                # Also check if result has items (for complex results)
                                if hasattr(context.result, 'items') and context.result.items:
                                    for item in context.result.items:
                                        if hasattr(item, 'text'):
                                            result_value += " " + str(item.text)
                                        elif hasattr(item, 'content'):
                                            result_value += " " + str(item.content)
                                
                                # Log the result content for debugging
                                logger.debug(f"Function {plugin_name}.{function_name} result content: {result_value[:300]}...")
                                
                                # Check for common error patterns in the result
                                error_patterns = [
                                    "failed",
                                    "error",
                                    "exception",
                                    "not found",
                                    "timeout",
                                    "unauthorized",
                                    "forbidden",
                                    "bad request",
                                    "internal error",
                                    "capacity not active",
                                    "capacitynotactive",  # Added for your specific error
                                    "connection failed",
                                    "invalid",
                                    "unable to",
                                    "graphql request failed",  # Added for GraphQL errors
                                    "failed to introspect",   # Added for schema introspection errors
                                    '"errorCode"',            # Added for JSON error responses
                                    '"message":'              # Added for structured error messages
                                ]
                                
                                result_lower = result_value.lower()
                                if any(pattern in result_lower for pattern in error_patterns):
                                    status = "error"
                                    logger.warning(f"Function {plugin_name}.{function_name} returned error result: {result_value[:200]}...")
                            
                        except Exception as e:
                            status = "error"
                            logger.error(f"Error in function {plugin_name}.{function_name}: {str(e)}")
                            raise
                        finally:
                            # End time for duration calculation
                            end_time = asyncio.get_event_loop().time()
                            
                            # Create completion info
                            completion_info = {
                                "type": "function_end",
                                "function": function_name,
                                "plugin": plugin_name,
                                "status": status,
                                "timestamp": end_time,
                                "start_timestamp": start_time  # Include start timestamp for duration calculation
                            }
                            
                            # Add result info if available
                            if hasattr(context, 'result') and context.result is not None:
                                result_value = str(context.result.value) if hasattr(context.result, 'value') else "N/A"
                                if len(result_value) > 100:
                                    result_value = f"{result_value[:97]}..."
                                completion_info["result"] = result_value
                            
                            # Add to function call stream
                            function_stream.add_function_call(completion_info)
                            
                            # Log the function completion with more context
                            duration_ms = (end_time - start_time) * 1000
                            logger.debug(f"{prefix} Function completed: {plugin_name}.{function_name} with status: {status} in {duration_ms:.2f}ms")

                # Add the auto function invocation filter
                kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, auto_function_filter)
                
                # Also add as regular function invocation filter for compatibility
                #kernel.add_filter(FilterTypes.FUNCTION_INVOCATION, auto_function_filter)
                    
            return kernel
