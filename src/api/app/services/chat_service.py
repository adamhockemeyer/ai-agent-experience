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
from app.services.file_processor import FileProcessor

from app.config.config import get_settings
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

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
        self.file_processor = FileProcessor()
        
    async def chat(self, session_id: str, agent: Agent, user_input: str, attachments: Optional[List[Attachment]] = None) -> AsyncGenerator[str, None]:
        """Process a chat request and generate a streaming response with optional attachments."""
        with tracer.start_as_current_span("chat") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("agent_id", agent.id)
            
            # Create kernel for this request
            kernel = await KernelFactory.create_kernel(agent, session_id=session_id)
            
            # Try to load existing thread first
            logger.info(f"🔍 Loading existing thread for session {session_id}")
            existing_thread = await self.thread_storage.load(session_id)
            logger.info(f"📄 Loaded existing_thread for session {session_id}: found={existing_thread is not None}, type={type(existing_thread)}")
            logger.debug(f"🔍 existing_thread repr: {repr(existing_thread)}")
            logger.debug(f"🔍 existing_thread bool evaluation: {bool(existing_thread)}")
            logger.info(f"existing_thread is None: {existing_thread is None}")
            logger.info(f"existing_thread == None: {existing_thread == None}")
            if existing_thread is not None:
                logger.info(f"📄 Found existing thread for session {session_id}")
                logger.info(f"🔍 existing_thread details: type={type(existing_thread)}, has_stored_messages={hasattr(existing_thread, '_stored_messages')}")
                logger.info(f"🔍 existing_thread class: {existing_thread.__class__}")
                logger.info(f"🔍 existing_thread module: {existing_thread.__class__.__module__}")
                
                # Log thread type details
                if isinstance(existing_thread, dict):
                    thread_type = existing_thread.get('thread_type', 'unknown')
                    logger.info(f"🔍 Dictionary thread with thread_type: {thread_type}")
                    if thread_type == "AzureAIAgentThread":
                        logger.info(f"🔗 AzureAIAgentThread dict with thread_id: {existing_thread.get('thread_id')}")
                elif hasattr(existing_thread, 'thread_type'):
                    logger.info(f"🔍 Object thread with thread_type: {existing_thread.thread_type}")
                    if existing_thread.thread_type == "AzureAIAgentThread":
                        logger.info(f"🔗 AzureAIAgentThread object with thread_id: {getattr(existing_thread, 'thread_id', 'no_id')}")
                
                if hasattr(existing_thread, '_stored_messages'):
                    logger.info(f"📊 existing_thread._stored_messages length: {len(existing_thread._stored_messages)}")
            else:
                logger.info("📭 No existing thread found for this session")
            
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
                    if existing_thread:
                        logger.info(f"🔍 Analyzing existing thread for session {session_id}: type={type(existing_thread)}")
                        
                        # Handle AzureAIAgentThread restoration
                        if isinstance(existing_thread, dict) and existing_thread.get('thread_type') == "AzureAIAgentThread":
                            if agent.agentType == "AzureAIAgent":
                                thread_id = existing_thread.get('thread_id')
                                logger.info(f"🔗 Found saved AzureAIAgentThread representation with ID: {thread_id} for session {session_id}")
                                logger.debug(f"🔍 AzureAIAgentThread representation details: {existing_thread}")
                            else:
                                logger.warning(f"⚠️  Found AzureAIAgentThread representation but agent type is {agent.agentType}, not AzureAIAgent")
                        # Handle legacy format
                        elif hasattr(existing_thread, 'thread_type') and existing_thread.thread_type == "AzureAIAgentThread":
                            if agent.agentType == "AzureAIAgent":
                                thread_id = getattr(existing_thread, 'thread_id', None)
                                logger.info(f"🔗 Found saved legacy AzureAIAgentThread with ID: {thread_id} for session {session_id}")
                            else:
                                logger.warning(f"⚠️  Found legacy AzureAIAgentThread but agent type is {agent.agentType}, not AzureAIAgent")
                        else:
                            logger.debug(f"🔍 Existing thread is not AzureAIAgentThread type: {type(existing_thread)} / {getattr(existing_thread, 'thread_type', 'no_thread_type')}")
                    else:
                        logger.info(f"📝 No existing thread found for session {session_id}")
                    
                    # Log thread_id decision
                    if thread_id:
                        logger.info(f"🎯 Will create agent with existing thread_id: {thread_id}")
                    else:
                        logger.info(f"🆕 Will create agent with new thread")
                    
                    # Create the agent using factory pattern - with thread_id if applicable
                    logger.info(f"🏭 Creating agent via factory: type={agent.agentType}, thread_id={thread_id}")
                    ai_agent_temp, thread_temp = await AgentFactory.create_agent(
                        kernel, 
                        agent, 
                        plugins,
                        thread_id=thread_id
                    )
                    # Apply proper type hints using Union for both agent types
                    ai_agent: Union[ChatCompletionAgent, AzureAIAgent] = cast(Union[ChatCompletionAgent, AzureAIAgent], ai_agent_temp)
                    thread: Union[ChatHistoryAgentThread, AzureAIAgentThread] = cast(Union[ChatHistoryAgentThread, AzureAIAgentThread], thread_temp)
                    
                    logger.info(f"🎉 Successfully created agent: {type(ai_agent).__name__} with thread: {type(thread).__name__}")
                    if hasattr(thread, 'id'):
                        logger.info(f"🆔 Thread ID: {getattr(thread, 'id', 'no_id')}")
                    
                    # Handle regular thread restoration for non-AzureAI threads
                    if existing_thread is not None:
                        logger.info(f"🔄 Processing existing thread for session {session_id}")
                        logger.debug(f"🔍 existing_thread type: {type(existing_thread)}, has_stored_messages: {hasattr(existing_thread, '_stored_messages')}")
                        
                        if hasattr(existing_thread, '_stored_messages'):
                            logger.info(f"📊 existing_thread has {len(existing_thread._stored_messages)} stored messages")
                        
                        # Skip AzureAIAgentThread since we already handled it above during agent creation
                        if isinstance(existing_thread, dict) and existing_thread.get('thread_type') == "AzureAIAgentThread":
                            if agent.agentType == "AzureAIAgent":
                                logger.info(f"✅ AzureAIAgentThread already handled during agent creation for session {session_id}")
                            else:
                                logger.warning(f"⚠️  Found AzureAIAgentThread representation but agent type mismatch, using new thread")
                        # Handle legacy AzureAIAgentThread format  
                        elif hasattr(existing_thread, 'thread_type') and existing_thread.thread_type == "AzureAIAgentThread":
                            if agent.agentType == "AzureAIAgent":
                                logger.info(f"✅ Legacy AzureAIAgentThread already handled during agent creation for session {session_id}")
                            else:
                                logger.warning(f"⚠️  Found legacy AzureAIAgentThread but agent type mismatch, using new thread")
                        # Use existing thread if it's the same type
                        elif type(existing_thread).__name__ == type(thread).__name__:
                            logger.info(f"Type check passed: existing_thread={type(existing_thread).__name__} matches thread={type(thread).__name__}")
                            logger.info(f"Using existing thread for session {session_id}")
                            thread = existing_thread
                            logger.info(f"After assignment: thread has _stored_messages={hasattr(thread, '_stored_messages')}")
                            
                            # Check if the restored thread has stored messages from before reduction
                            if hasattr(thread, '_stored_messages') and thread._stored_messages:
                                logger.info(f"Found {len(thread._stored_messages)} stored messages from previous session for {session_id}")
                                logger.debug(f"Sample stored messages: {[f'[{msg.role}] {msg.content[:50]}...' for msg in thread._stored_messages[:3]]}")
                                
                                # CRITICAL: Add the stored messages back to the thread to restore conversation history
                                # This is necessary for the agent to have access to previous conversation context
                                for stored_message in thread._stored_messages:
                                    thread._chat_history.add_message(stored_message)
                                
                                logger.info(f"Restored {len(thread._stored_messages)} messages to thread for session {session_id}")
                                # Clear the stored messages since they're now in the thread
                                thread._stored_messages = []
                            else:
                                logger.info(f"No stored messages found in restored thread for {session_id}: has_attr={hasattr(thread, '_stored_messages')}, is_empty={not getattr(thread, '_stored_messages', None)}")
                        else:
                            logger.warning(f"Existing thread type {type(existing_thread).__name__} not compatible with {type(thread).__name__}, using new thread")
                    else:
                        logger.info(f"No existing thread found for session {session_id}, using new thread")
                
                    # IMPORTANT: Re-apply reducer configuration for both new and restored threads
                    # This ensures that restored threads from storage also have the reducer properly configured
                    logger.info(f"🔧 Checking reducer conditions - enableHistoryReduction: {agent.enableHistoryReduction}, has_chat_history: {hasattr(thread, '_chat_history')}")
                    if agent.enableHistoryReduction and hasattr(thread, '_chat_history'):
                        # Import here to avoid circular imports
                        from semantic_kernel.contents import ChatHistorySummarizationReducer
                        
                        logger.info(f"🔧 Current chat history type: {type(thread._chat_history).__name__}")
                        
                        # Check if it's already a reducer with correct configuration
                        if isinstance(thread._chat_history, ChatHistorySummarizationReducer):
                            # Check if the configuration matches
                            current_target = getattr(thread._chat_history, '_target_count', None)
                            current_threshold = getattr(thread._chat_history, '_threshold_count', None)
                            
                            if current_target == agent.reducerMsgCount and current_threshold == agent.reducerThreshold:
                                logger.info(f"✅ Reducer already properly configured with target={current_target}, threshold={current_threshold}")
                            else:
                                logger.info(f"🔧 Reducer configuration mismatch - current: target={current_target}, threshold={current_threshold}, expected: target={agent.reducerMsgCount}, threshold={agent.reducerThreshold}")
                                # Need to re-apply with correct configuration
                                need_reapply = True
                        else:
                            logger.info(f"🔧 Chat history is not a reducer, need to apply reducer configuration")
                            need_reapply = True
                        
                        # Only re-apply if needed
                        if 'need_reapply' in locals() and need_reapply:
                            logger.info(f"🔧 Applying chat history reducer to thread for session {session_id}")
                            # Create the reducer with the same service used by the agent
                            try:
                                logger.info(f"🔧 Starting reducer application process...")
                                # Get the service from the ai_agent kernel (not the agent model)
                                service = None
                                if hasattr(ai_agent, 'kernel') and ai_agent.kernel:
                                    chat_services = ai_agent.kernel.get_services_by_type(ChatCompletionClientBase)
                                    if chat_services:
                                        service = list(chat_services.values())[0]
                                        logger.info(f"🔧 Found chat service from ai_agent.kernel: {type(service).__name__}")
                                elif hasattr(agent, '_kernel') and agent._kernel:
                                    chat_services = agent._kernel.get_services_by_type(ChatCompletionClientBase)
                                    if chat_services:
                                        service = list(chat_services.values())[0]
                                        logger.info(f"🔧 Found chat service from agent._kernel: {type(service).__name__}")
                                
                                if service:
                                    logger.info(f"🔧 Creating reducer with target_count={agent.reducerMsgCount}, threshold_count={agent.reducerThreshold}")
                                    history_reducer = ChatHistorySummarizationReducer(
                                        target_count=agent.reducerMsgCount,
                                        threshold_count=agent.reducerThreshold,
                                        service=service
                                    )
                                    
                                    # Store existing messages if any
                                    existing_messages = []
                                    if hasattr(thread._chat_history, 'messages') and thread._chat_history.messages:
                                        existing_messages = list(thread._chat_history.messages)
                                        logger.info(f"🔧 Found {len(existing_messages)} existing messages to preserve")
                                    
                                    # Replace the chat history with the reducer
                                    logger.info(f"🔧 Replacing chat history with reducer...")
                                    thread._chat_history = history_reducer
                                    
                                    # Restore the existing messages to the reducer
                                    for msg in existing_messages:
                                        thread._chat_history.add_message(msg)
                                    
                                    logger.info(f"✅ Successfully applied reducer to thread: {type(thread._chat_history).__name__} with {len(existing_messages)} messages")
                                else:
                                    logger.warning(f"❌ Could not find chat service for reducer configuration")
                                    logger.info(f"🔧 Debug: ai_agent has kernel: {hasattr(ai_agent, 'kernel')}, agent has _kernel: {hasattr(agent, '_kernel')}")
                            except Exception as e:
                                logger.error(f"❌ Failed to apply reducer to thread: {e}", exc_info=True)
                
                    # Create a queue for merging content and function call events
                    merged_queue = asyncio.Queue()
                    
                    # Define a task to process the content stream
                    async def process_content_stream():
                        nonlocal thread
                        try:
                            # Process user input and attachments
                            content_items = await self._create_message_content_items(user_input, attachments or [], agent, function_stream)
                            
                            # Create a ChatMessageContent with the role USER
                            chat_message = ChatMessageContent(role=AuthorRole.USER, items=content_items)
                            
                            # Track active function calls to analyze results
                            active_function_calls = {}
                            
                            # Invoke the agent with the chat message
                            logger.info(f"Invoking agent with {len(content_items)} content items")
                            async for response in ai_agent.invoke_stream(
                                messages=chat_message,
                                thread=thread
                            ):
                                # Update thread from response
                                thread = response.thread
                                
                                # Debug logging for response structure
                                logger.debug(f"Response type: {type(response)}, has thread: {hasattr(response, 'thread')}")
                                if hasattr(response, 'thread') and response.thread:
                                    logger.debug(f"Thread type: {type(response.thread)}, has messages: {hasattr(response.thread, 'messages')}")
                                    if hasattr(response.thread, 'messages'):
                                        logger.debug(f"Thread has {len(response.thread.messages)} messages")
                                
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
                            # Process events from function stream with immediate yielding
                            async for event in function_stream.get_events():
                                await merged_queue.put({
                                    "type": "function_call",
                                    "content": event
                                })
                                # Force immediate processing by yielding control
                                await asyncio.sleep(0)
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
                            # Yield the item from the queue immediately
                            yield item["content"]
                            # For function calls, add a minimal delay to ensure immediate processing
                            if item.get("type") == "function_call":
                                await asyncio.sleep(0)
                    
                    # Wait for both tasks to complete
                    await asyncio.gather(content_task, function_task)
                    
                    # Attempt chat history reduction if enabled and applicable
                    if thread and agent.enableHistoryReduction:
                        try:
                            # Only attempt reduction for ChatHistoryAgentThread (ChatCompletionAgent)
                            if isinstance(thread, ChatHistoryAgentThread):
                                current_msg_count = len(thread)
                                logger.info(f"Chat history reduction enabled for session {session_id}. Current message count: {current_msg_count}")
                                
                                # Detailed debugging: check how message count is calculated
                                logger.debug(f"🔍 Thread length calculation: len(thread)={len(thread)}")
                                if hasattr(thread, '_chat_history') and hasattr(thread._chat_history, 'messages'):
                                    actual_msg_count = len(thread._chat_history.messages) if thread._chat_history.messages else 0
                                    logger.debug(f"🔍 Actual _chat_history.messages count: {actual_msg_count}")
                                
                                # Log reducer configuration if available
                                if hasattr(thread, '_chat_history') and hasattr(thread._chat_history, 'target_count'):
                                    target_count = getattr(thread._chat_history, 'target_count', 'unknown')
                                    threshold_count = getattr(thread._chat_history, 'threshold_count', 'unknown')
                                    trigger_threshold = target_count + threshold_count if isinstance(target_count, int) and isinstance(threshold_count, int) else 'unknown'
                                    logger.info(f"📊 Reducer config: target_count={target_count}, threshold_count={threshold_count}, triggers_at={trigger_threshold}")
                                    
                                    if isinstance(trigger_threshold, int):
                                        should_reduce = current_msg_count >= trigger_threshold
                                        logger.info(f"🎯 Should reduce? {current_msg_count} >= {trigger_threshold} = {should_reduce}")
                                
                                logger.info(f"Attempting chat history reduction for session {session_id}")
                                
                                # Let's inspect the reducer state before calling reduce()
                                if hasattr(thread, '_chat_history'):
                                    chat_history = thread._chat_history
                                    logger.info(f"🔍 Chat history type: {type(chat_history).__name__}")
                                    if hasattr(chat_history, 'target_count') and hasattr(chat_history, 'threshold_count'):
                                        logger.info(f"🔍 Reducer attributes: target={chat_history.target_count}, threshold={chat_history.threshold_count}")
                                    if hasattr(chat_history, 'messages'):
                                        logger.info(f"🔍 Chat history messages count: {len(chat_history.messages) if chat_history.messages else 0}")
                                
                                logger.info(f"🎯 Calling thread.reduce() for session {session_id}")
                                is_reduced = await thread.reduce()
                                logger.info(f"🔍 Reduce operation returned: {is_reduced} (type: {type(is_reduced)})")
                                if is_reduced:
                                    new_msg_count = len(thread)
                                    logger.info(f"✅ Chat history REDUCED for session {session_id}: {current_msg_count} → {new_msg_count} messages")
                                    
                                    # Log summary if present for debugging
                                    async for msg in thread.get_messages():
                                        if msg.metadata and msg.metadata.get("__summary__"):
                                            logger.info(f"📝 Summary created: {msg.content[:100]}...")
                                            break
                                    
                                    # After reduction, create a new thread without reducer for serialization
                                    # This avoids the pickle issue with ChatHistorySummarizationReducer
                                    if hasattr(thread, 'chat_history') and hasattr(thread.chat_history, 'messages'):
                                        logger.debug(f"Creating new thread without reducer for serialization")
                                        new_thread = ChatHistoryAgentThread()
                                        # Copy the reduced messages to the new thread
                                        for msg in thread.chat_history.messages:
                                            new_thread._chat_history.add_message(msg)
                                        thread = new_thread
                                else:
                                    logger.info(f"ℹ️  No reduction needed for session {session_id} - current message count: {current_msg_count}")
                            else:
                                logger.debug(f"Chat history reduction not applicable for thread type: {type(thread).__name__}")
                        except Exception as reduction_error:
                            logger.warning(f"Error during chat history reduction for session {session_id}: {str(reduction_error)}")
                            # Don't fail the entire chat operation due to reduction error
                    else:
                        if thread:
                            logger.debug(f"Chat history reduction disabled for session {session_id} (enableHistoryReduction={agent.enableHistoryReduction})")
                        else:
                            logger.debug(f"No thread available for reduction for session {session_id}")
                            logger.warning(f"Error during chat history reduction for session {session_id}: {str(reduction_error)}")
                            # Don't fail the entire chat operation due to reduction error
                    
                    # Persist thread after successful completion
                    if thread:
                        logger.info(f"💾 Persisting thread for session {session_id}")
                        logger.debug(f"🔍 Thread to persist: type={type(thread).__name__}, id={getattr(thread, 'id', 'no_id')}")
                        
                        await self.thread_storage.save(session_id, thread)
                        logger.info(f"✅ Successfully saved thread for session {session_id}")
                    else:
                        logger.warning(f"⚠️  No thread to persist for session {session_id}")
                    
            except Exception as e:
                logger.error(f"Error in chat: {str(e)}", exc_info=True)
                span.record_exception(e)
                yield f"Error: {str(e)}"
            
            finally:
                # Clean up function call stream
                if agent.displayFunctionCallStatus:
                    FunctionCallStream.cleanup(session_id)

    async def _create_message_content_items(self, user_input: str, attachments: List[Attachment], agent: Agent, function_stream=None) -> List[Union[TextContent, ImageContent]]:
        """Create content items for chat messages from user input and attachments.
        
        This method processes both the user's text input and any file attachments to create
        a complete list of content items (TextContent and ImageContent) that can be sent
        to the chat agent. Images are converted to ImageContent when possible, while
        documents are processed and included as text content.
        
        Args:
            user_input: The user's text input
            attachments: List of file attachments to process
            agent: The agent configuration containing model information
        
        Returns:
            List of content items (TextContent and ImageContent) for the chat message
        """
        content_items = []
        
        if not attachments:
            content_items.append(TextContent(text=user_input))
            return content_items
        
        # Send initial status if function stream is available and there are attachments
        overall_start_time = asyncio.get_event_loop().time()
        if function_stream:
            function_stream.add_function_call({
                "type": "function_start",
                "plugin": "FileProcessor",
                "function": "process_attachments",
                "arguments": {"count": len(attachments), "status": f"🔄 Processing {len(attachments)} attachment(s)..."},
                "is_auto": "Manual",
                "timestamp": overall_start_time
            })
        
        processed_content_parts = []
        image_attachments_processed = 0
        document_attachments_processed = 0
        
        try:
            for idx, attachment in enumerate(attachments):
                logger.info(f"Processing attachment {idx+1}/{len(attachments)}: {attachment.name}")
                
                # Record start time for duration calculation
                start_time = asyncio.get_event_loop().time()
                
                # Send processing status to function stream if available
                if function_stream:
                    function_stream.add_function_call({
                        "type": "function_start",
                        "plugin": "FileProcessor",
                        "function": f"process_file_{idx+1}",
                        "arguments": {"filename": attachment.name, "progress": f"{idx+1}/{len(attachments)}"},
                        "is_auto": "Manual",
                        "timestamp": start_time
                    })
                
                # Use FileProcessor to handle the attachment
                processed_content, metadata = await self.file_processor.process_file_attachment(attachment)
                
                if metadata["type"] == "image":
                    # For images, add as ImageContent (let the system error if model doesn't support it)
                    try:
                        mime_type = metadata["mime_type"].split(';')[0] if metadata["mime_type"] else "image/jpeg"
                        image_content = ImageContent(
                            data=processed_content,  # Base64 string from FileProcessor
                            data_format="base64",
                            mime_type=mime_type
                        )
                        content_items.append(image_content)
                        image_attachments_processed += 1
                        
                        logger.info(f"Added image as ImageContent: {attachment.name}")
                        # Function call status is handled by the overall completion message
                            
                    except Exception as img_error:
                        logger.error(f"Error creating ImageContent for {attachment.name}: {str(img_error)}")
                        # Fall back to text description
                        processed_content_parts.append(f"[Image: {attachment.name}]")
                
                elif metadata["type"] == "document":
                    # For documents, add the markdown content to the text
                    processed_content_parts.append(processed_content)
                    document_attachments_processed += 1
                    
                    logger.info(f"Added document as text: {attachment.name}")
                    # Function call status is handled by the overall completion message
                
                elif metadata["type"] == "error":
                    # Add error information to text
                    processed_content_parts.append(processed_content)
                    logger.warning(f"Error processing attachment {attachment.name}")
        
            # Combine user input with processed attachment content
            if processed_content_parts:
                combined_text = user_input + "\n\n" + "\n\n".join(processed_content_parts)
            else:
                combined_text = user_input
            
            content_items.insert(0, TextContent(text=combined_text))
            
            logger.info(f"Processed {image_attachments_processed} images and {document_attachments_processed} documents")
            
            # Send final processing summary to function stream if available
            if function_stream and (image_attachments_processed > 0 or document_attachments_processed > 0):
                end_time = asyncio.get_event_loop().time()
                function_stream.add_function_call({
                    "type": "function_end",
                    "plugin": "FileProcessor",
                    "function": "process_attachments",
                    "status": "success",
                    "result": f"📁 Processing complete: {image_attachments_processed} images, {document_attachments_processed} documents",
                    "is_auto": "Manual",
                    "timestamp": end_time,
                    "start_timestamp": overall_start_time
                })
        
        except Exception as processing_error:
            # If attachment processing fails, fall back to text-only with user input
            logger.error(f"Error processing attachments: {str(processing_error)}")
            content_items = [TextContent(text=user_input)]
            logger.info("Using text-only content due to attachment processing error")
        
        return content_items

    def _format_openapi_error(self, error: OpenAPIPluginError) -> str:
        """Format OpenAPI plugin error into a user-friendly message."""
        return f"Error with OpenAPI plugin '{error.tool_name}' (ID: {error.tool_id}): {error.message}"


