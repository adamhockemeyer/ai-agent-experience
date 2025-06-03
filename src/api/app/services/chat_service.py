# app/services/chat_service.py
import asyncio
import json
import logging
import base64
import os
import re
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple, Union, cast, TypeVar, Generic
from opentelemetry import trace

from app.models import Agent, Attachment
from app.agents.agent_factory import AgentFactory
from app.plugins.plugin_manager import PluginManager
from app.plugins.openapi_plugin import OpenAPIPluginError
from app.services.kernel_factory import KernelFactory
from app.services.thread_storage import ThreadStorage
from app.services.function_call_stream import FunctionCallStream
from app.config.config import get_settings

# Semantic Kernel imports for multimodal support
from semantic_kernel.contents import ImageContent, TextContent, ChatMessageContent
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread, AzureAIAgent, AzureAIAgentThread

# Get a tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, thread_storage: ThreadStorage):
        self.thread_storage = thread_storage
        
    async def chat(self, session_id: str, agent: Agent, user_input: str, attachments: Optional[List[Attachment]] = None) -> AsyncGenerator[str, None]:
        """Process a chat request and generate a streaming response with optional attachments."""
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
                    ai_agent_temp, thread_temp = await AgentFactory.create_agent(
                        kernel, 
                        agent, 
                        plugins,
                        thread_id=thread_id
                    )
                    # Apply proper type hints using Union for both agent types
                    ai_agent: Union[ChatCompletionAgent, AzureAIAgent] = cast(Union[ChatCompletionAgent, AzureAIAgent], ai_agent_temp)
                    thread: Union[ChatHistoryAgentThread, AzureAIAgentThread] = cast(Union[ChatHistoryAgentThread, AzureAIAgentThread], thread_temp)
                    
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
                            # Check if we need to use multimodal processing
                            use_multimodal = attachments and self._is_vision_capable_model(agent.modelSelection.model)                            # Create a ChatMessageContent object with the user's input
                            content_items = []
                            content_items.append(TextContent(text=user_input))
                            image_attachments_processed = 0
                            
                            # Process image attachments if the model supports vision
                            if use_multimodal and attachments:
                                try:
                                    # Process image attachments
                                    for idx, attachment in enumerate(attachments):
                                        if attachment.type.startswith('image/'):
                                            try:
                                                # For data URLs from the frontend
                                                if attachment.url.startswith('data:') and ';base64,' in attachment.url:
                                                    # Split the URL to ensure proper formatting
                                                    url_parts = attachment.url.split(';base64,', 1)
                                                    if len(url_parts) == 2:
                                                        mime_part = url_parts[0]
                                                        base64_data = url_parts[1]
                                                        
                                                        # Clean up the MIME part to ensure it's exactly "data:image/type"
                                                        mime_type = mime_part.replace('data:', '')
                                                        
                                                        # Extract just the base64 encoded data (without the data URL prefix)
                                                        # And use it with data_format="base64"
                                                        logger.info(f"Creating ImageContent with base64 data for {attachment.name}")
                                                        image_content = ImageContent(
                                                            data=base64_data,  # Just the base64 string, not the full data URI
                                                            data_format="base64",  # Specify the data format as base64
                                                            mime_type=mime_type  # The MIME type (like "image/jpeg")
                                                        )
                                                    else:
                                                        logger.error(f"Invalid data URL format for {attachment.name}")
                                                        continue

                                                # For HTTP URLs
                                                elif attachment.url.startswith('http'):
                                                    # Use uri parameter instead of url for HTTP URLs
                                                    image_content = ImageContent(uri=attachment.url)
                                                    logger.info(f"Using HTTP URL for image {attachment.name}")

                                                # For binary data or other formats
                                                else:
                                                    try:
                                                        # Extract binary data and convert to base64 string
                                                        binary_data = self._extract_base64_image_data(attachment.url)
                                                        base64_str = base64.b64encode(binary_data).decode('ascii')
                                                        
                                                        # Use proper parameters according to documentation
                                                        mime_type = attachment.type.split(';')[0] if attachment.type else "image/jpeg"
                                                        image_content = ImageContent(
                                                            data=base64_str,  # Base64 encoded string
                                                            data_format="base64",  # Specify the format as base64
                                                            mime_type=mime_type  # The MIME type
                                                        )
                                                        logger.info(f"Created ImageContent with base64 data for {attachment.name}")
                                                    except Exception as extract_error:
                                                        logger.error(f"Error creating ImageContent: {str(extract_error)}")
                                                        continue
                                                
                                                # Add to the content items
                                                content_items.append(image_content)
                                                image_attachments_processed += 1
                                                logger.info(f"Added image {idx+1}/{len(attachments)}: {attachment.name}")
                                            except Exception as img_error:
                                                # If there's an error processing the image, log it and skip this image
                                                logger.error(f"Error processing image attachment {attachment.name}: {str(img_error)}")
                                    
                                    logger.info(f"Processed {image_attachments_processed} image attachments for multimodal input")
                                except Exception as mm_error:
                                    # If multimodal processing fails, fall back to text-only
                                    logger.error(f"Error in multimodal processing: {str(mm_error)}")
                                    # Reset content items to just the text input without image descriptions
                                    content_items = [TextContent(text=user_input)]
                                    logger.info("Using text-only content due to multimodal processing error")
                            
                            # Create a ChatMessageContent with the role USER
                            chat_message = ChatMessageContent(role=AuthorRole.USER, items=content_items)
                            
                            # Invoke the agent with the chat message
                            logger.info(f"Invoking agent with {len(content_items)} content items")
                            async for response in ai_agent.invoke_stream(
                                messages=chat_message,
                                thread=thread
                            ):
                                # Update thread from response
                                thread = response.thread
                                
                                # Extract content from response
                                if hasattr(response, 'content'):
                                    content = response.content
                                else:
                                    content = str(response)
                                
                                # Add to the queue
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
        
    def _is_vision_capable_model(self, model_name: str) -> bool:
        """Assume model is vision-capable; rely on user knowledge or error handling elsewhere."""
        # No hardcoded list; always return True. If the model is not vision-capable, error handling will occur downstream.
        return True
    
    def _extract_base64_image_data(self, data_url: str) -> bytes:
        """Extract binary image data from a base64 data URL."""
        try:
            # Check if this is a data URL
            if data_url.startswith('data:'):
                # Regular expression to extract base64 data from data URL
                pattern = r'data:(?:image\/[^;]+);base64,(.+)'
                match = re.match(pattern, data_url)
                
                if not match:
                    # Try a more permissive pattern
                    pattern = r'data:.*?;base64,(.+)'
                    match = re.match(pattern, data_url)
                    
                if not match:
                    raise ValueError(f"Invalid data URL format: {data_url[:50]}...")
                    
                base64_data = match.group(1)
            else:
                # Assume it's already a base64 string
                base64_data = data_url
            
            # Remove any whitespace from the base64 string
            base64_data = base64_data.strip()
            
            # Ensure the base64 data has valid padding
            padding_needed = len(base64_data) % 4
            if padding_needed > 0:
                base64_data += '=' * (4 - padding_needed)
            
            # Decode the base64 data to binary
            binary_data = base64.b64decode(base64_data)
            return binary_data
        
        except Exception as e:
            logger.error(f"Error extracting base64 data: {str(e)}")
            raise
        
    def _log_image_url_debug(self, url: str, name: str):
        """Log a debug sample of the image URL for troubleshooting."""
        if url.startswith('data:'):
            # For data URLs, log the format and first few chars of base64 data
            parts = url.split(',', 1)
            header = parts[0]
            data_sample = parts[1][:30] + '...' if len(parts) > 1 else 'No data'
            logger.debug(f"Image {name} URL format: {header}, data sample: {data_sample}")
        else:
            # For HTTP URLs, log the full URL (or truncate if very long)
            log_url = url if len(url) < 100 else url[:97] + '...'
            logger.debug(f"Image {name} URL: {log_url}")
