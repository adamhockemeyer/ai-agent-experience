# app/services/chat_service.py
import asyncio
import json
import logging
from typing import Dict, Any, AsyncGenerator
from opentelemetry import trace

from app.models import Agent
from app.agents.agent_factory import AgentFactory
from app.plugins.plugin_manager import PluginManager
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
                    plugins = await plugin_manager.initialize_plugins(agent)
                    
                    # Create the agent using factory pattern
                    ai_agent, thread = await AgentFactory.create_agent(
                        kernel, agent, plugins
                    )
                    
                    # Use existing thread if available and compatible
                    if existing_thread and isinstance(existing_thread, type(thread)):
                        logger.info(f"Using existing thread for session {session_id}")
                        thread = existing_thread
                    
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