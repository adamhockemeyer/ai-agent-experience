# app/services/chat_service.py
import asyncio
import json
import logging
from typing import Dict, Any, AsyncGenerator
from opentelemetry import trace

from app.models import Agent
from app.agents.agent_factory import AgentFactory
from app.plugins.plugin_manager import PluginManager
from app.plugins.openapi_plugin import OpenAPIPluginError
from app.services.kernel_factory import KernelFactory
from app.services.thread_storage import ThreadStorage
from app.services.function_call_stream import FunctionCallStream
from app.config.config import get_settings

# Get a tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, thread_storage: ThreadStorage):
        self.thread_storage = thread_storage
        
    async def chat(self, session_id: str, agent: Agent, user_input: str) -> AsyncGenerator[str, None]:
        """Process a chat request and generate a streaming response."""
        with tracer.start_as_current_span("chat") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("agent_id", agent.id)
            
            # Create kernel for this request
            kernel = await KernelFactory.create_kernel(agent, session_id=session_id)
            
            # Try to load existing thread first
            existing_thread = await self.thread_storage.load(session_id)
            
            # If function call status should be displayed, prepare the function call stream
            function_stream = None
            if agent.displayFunctionCallStatus:
                function_stream = FunctionCallStream.get_or_create(session_id)
            
            # Define thread at the method level so it can be shared
            thread = None
            
            try:
                async with PluginManager() as plugin_manager:
                    # Initialize plugins for this agent
                    try:
                        plugins = await plugin_manager.initialize_plugins(agent)
                    except OpenAPIPluginError as ope:
                        # Format a user-friendly error message for OpenAPI plugin issues
                        error_message = self._format_openapi_error(ope)
                        logger.error(f"OpenAPI plugin error: {error_message}")
                        span.set_attribute("error", "openapi_plugin_error")
                        span.set_attribute("error.message", ope.message)
                        span.set_attribute("error.tool_id", ope.tool_id)
                        span.set_attribute("error.tool_name", ope.tool_name)
                        yield error_message
                        return
                    
                    # Check for existing thread first to make decisions about agent creation
                    thread_id = None
                    if existing_thread and hasattr(existing_thread, 'thread_type') and existing_thread.thread_type == "AzureAIAgentThread":
                        if agent.agentType == "AzureAIAgent":
                            logger.info(f"Found saved AzureAIAgentThread with ID: {existing_thread.thread_id} for session {session_id}")
                            thread_id = existing_thread.thread_id
                    
                    # Create the agent using factory pattern - with thread_id if applicable
                    ai_agent, thread = await AgentFactory.create_agent(
                        kernel, 
                        agent, 
                        plugins,
                        thread_id=thread_id
                    )
                    
                    # Handle regular thread restoration for non-AzureAI threads
                    if existing_thread:
                        # Skip AzureAIAgentThread since we already handled it above
                        if hasattr(existing_thread, 'thread_type') and existing_thread.thread_type == "AzureAIAgentThread":
                            if agent.agentType == "AzureAIAgent":
                                logger.info(f"Using restored AzureAIAgentThread with ID: {existing_thread.thread_id} for session {session_id}")
                            else:
                                logger.warning(f"Found AzureAIAgentThread ID but agent is not AzureAIAgent type, using new thread")
                        # Use existing thread if it's the same type
                        elif isinstance(existing_thread, type(thread)):
                            logger.info(f"Using existing thread for session {session_id}")
                            thread = existing_thread
                        else:
                            logger.warning(f"Existing thread type {type(existing_thread)} not compatible with {type(thread)}, using new thread")
                    
                    # Create a queue for merging content and function call events
                    merged_queue = asyncio.Queue()
                    
                    # Define a task to process the content stream
                    async def process_content_stream():
                        nonlocal thread
                        try:
                            async for response in ai_agent.invoke_stream(
                                messages=user_input, 
                                thread=thread
                            ):
                                # Update thread from response
                                thread = response.thread
                                
                                # Extract content from response
                                if hasattr(response, 'content'):
                                    content = response.content
                                else:
                                    content = str(response)
                                    
                                # Put content in the merged queue
                                await merged_queue.put({
                                    "type": "content", 
                                    "content": content
                                })
                                
                        except Exception as e:
                            # Put the error in the queue
                            logger.error(f"Error in content stream: {str(e)}", exc_info=True)
                            await merged_queue.put({
                                "type": "error",
                                "content": f"Error: {str(e)}"
                            })
                        finally:
                            # Mark the content stream as done by putting None
                            await merged_queue.put(None)
                            
                            # Close the function stream when content stream is done
                            # This is the key fix - ensure function_stream is closed when main content is done
                            if function_stream:
                                logger.info(f"Main content stream complete, closing function stream for session {session_id}")
                                function_stream.close()
                    
                    # Define a task to process function call events
                    async def process_function_calls():
                        if not function_stream:
                            # No function stream, just mark as done
                            await merged_queue.put(None)
                            return
                        
                        try:
                            # Process events from function stream
                            async for event in function_stream.get_events():
                                await merged_queue.put({
                                    "type": "function_call",
                                    "content": event
                                })
                        except Exception as e:
                            logger.error(f"Error processing function calls: {str(e)}", exc_info=True)
                        finally:
                            # Mark function call stream as done
                            await merged_queue.put(None)
                    
                    # Start both tasks
                    content_task = asyncio.create_task(process_content_stream())
                    function_task = asyncio.create_task(process_function_calls())
                    
                    # Count of active streams
                    active_streams = 2
                    
                    # Process the merged queue
                    while active_streams > 0:
                        item = await merged_queue.get()
                        if item is None:
                            # One of the streams is done
                            active_streams -= 1
                        else:
                            # Yield the item from the queue
                            yield item["content"]
                    
                    # Wait for both tasks to complete
                    await asyncio.gather(content_task, function_task)
                    
                    # Persist thread after successful completion
                    if thread:
                        await self.thread_storage.save(session_id, thread)
                        logger.info(f"Saved thread for session {session_id}")
                    
            except Exception as e:
                logger.error(f"Error in chat: {str(e)}", exc_info=True)
                span.record_exception(e)
                yield f"Error: {str(e)}"
            
            finally:
                # Clean up function call stream
                if agent.displayFunctionCallStatus:
                    FunctionCallStream.cleanup(session_id)
    
    def _format_openapi_error(self, error: OpenAPIPluginError) -> str:
        """Format OpenAPI plugin error into a user-friendly message."""
        return f"Error with OpenAPI plugin '{error.tool_name}' (ID: {error.tool_id}): {error.message}"