import asyncio
import logging
import json
import os
import platform
import subprocess
import shutil
from typing import Dict, Any, AsyncGenerator
from opentelemetry import trace
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread, AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from semantic_kernel.functions import KernelArguments, kernel_function
from semantic_kernel.contents import FunctionCallContent, FunctionResultContent
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.filters import FunctionInvocationContext
from semantic_kernel.connectors.mcp import MCPStdioPlugin
from app.models import Agent
from app.plugins.mcp import MCPPluginManager, create_mcp_config_from_json
from app.services.kernel_factory import KernelFactory, function_call_queues
from app.services.thread_storage import ThreadStorage, InMemoryThreadStorage, RedisThreadStorage, CosmosDbThreadStorage
from app.config.config import get_settings

# Get a tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        # Get application settings
        settings = get_settings()
        
        # Initialize storage based on configuration
        storage_type = settings.thread_storage_type.lower()
        
        if storage_type == "redis":
            self.thread_storage = RedisThreadStorage(
                connection_string=settings.redis_connection_string,
                ttl_seconds=settings.thread_ttl_seconds
            )
        elif storage_type == "cosmosdb":
            self.thread_storage = CosmosDbThreadStorage(
                connection_string=settings.cosmos_db_connection_string,
                endpoint=settings.cosmos_db_endpoint,
                database_name=settings.cosmos_db_database_name,
                container_name=settings.cosmos_db_container_name,
                partition_key=settings.cosmos_db_partition_key,
                ttl_seconds=settings.thread_ttl_seconds
            )
        else:  # Default to memory storage
            self.thread_storage = InMemoryThreadStorage()
        
        logger.info(f"Using {storage_type} for thread storage")

    async def chat(self, session_id: str, agent: Agent, user_input: str) -> AsyncGenerator[str, None]:
        """Process a chat request and generate a streaming response."""
        plugin_manager = None
        mcp_plugin = None
        
        with tracer.start_as_current_span("chat") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("agent_id", agent.id)
            span.set_attribute("user_input_length", len(user_input))
            
            try:
                # Create kernel for this request
                kernel = await KernelFactory.create_kernel(agent, session_id=session_id)
                kernel_settings = PromptExecutionSettings(function_choice_behavior=FunctionChoiceBehavior.Auto())

                # Try to load existing thread first
                existing_thread = await self.thread_storage.load(session_id)
            
                # Select the appropriate agent type based on agent properties
                if agent.agentType == "AzureAIAgent":
                    ai_agent, thread = await self._create_azure_ai_agent(kernel, agent, kernel_settings)
                    # Use existing thread if available
                    if existing_thread and isinstance(existing_thread, AzureAIAgentThread):
                        thread = existing_thread
                elif agent.agentType == "ChatCompletionAgent":
                    ai_agent, thread = await self._create_chat_completion_agent(kernel, agent, kernel_settings)
                    # Capture plugin_manager reference for cleanup if it was created
                    if hasattr(self, '_plugin_manager'):
                        plugin_manager = self._plugin_manager
                    if hasattr(self, '_mcp_plugin'):
                        mcp_plugin = self._mcp_plugin
                    # Use existing thread if available
                    if existing_thread and isinstance(existing_thread, ChatHistoryAgentThread):
                        thread = existing_thread
                else:
                    raise ValueError(f"Unsupported agent type: {agent.agentType}")
            
                # Execute chat completion using the agent's invoke method
                with tracer.start_as_current_span("execute_invoke_stream") as completion_span:
                    completion_span.set_attribute("provider", agent.modelSelection.provider)
                    completion_span.set_attribute("model", agent.modelSelection.model)
                    completion_span.set_attribute("agent_type", agent.agentType) 

                    # Generate the streamed agent response(s)
                    async for response in ai_agent.invoke_stream(
                        messages=user_input, 
                        thread=thread
                    ):
                        # Process the response and yield results
                        async for chunk in self._process_function_call_updates(session_id):
                            yield chunk
                        
                        # Update thread with the latest response
                        thread = response.thread

                        # Process the normal response content
                        yield response.content
                
                    # Process any final function calls and clean up
                    async for chunk in self._process_final_function_calls(session_id):
                        yield chunk
                        
                    # Persist the thread to storage
                    if thread is not None:
                        await self.thread_storage.save(session_id, thread)
                        logger.info(f"Persisted thread for session {session_id}")
                    
                    logger.info(f"Chat completed successfully for session {session_id} with agent {agent.id}")
                    
            except Exception as e:
                # Log the error
                logger.error(f"Semantic Kernel error in chat: {str(e)}", exc_info=True)
                # Set error attributes on span
                span.record_exception(e)
                span.set_attribute("error", str(e))

                # Yield a structured error response that the chat route can identify
                yield {"error": f"Error when invoking stream: {str(e)}"}
                
            finally:

                if mcp_plugin is not None:
                    try:
                        logger.info(f"Explicitly closing MCP plugin for session {session_id}")
                        await mcp_plugin.close()
                        self._mcp_plugin = None
                    except Exception as disconnect_error:
                        logger.warning(f"Error during MCP plugin disconnect: {str(disconnect_error)}")
    
                # Clean up MCP plugin manager regardless of success or failure
                if plugin_manager is not None:
                    try:
                        logger.info(f"Cleaning up MCP plugin manager for session {session_id}")
                        await plugin_manager.__aexit__(None, None, None)
                        self._plugin_manager = None
                    except Exception as cleanup_error:
                        logger.warning(f"Error during final MCP plugin cleanup: {str(cleanup_error)}")

    # async def chat(self, session_id: str, agent: Agent, user_input: str) -> AsyncGenerator[str, None]:
    #     """Process a chat request and generate a streaming response.
        
    #     Args:
    #         session_id: Unique identifier for the conversation session
    #         agent: Agent configuration including model, system prompt, and tools
    #         user_input: The user's message text
            
    #     Returns:
    #         AsyncGenerator yielding response content chunks as they're generated
            
    #     Raises:
    #         ValueError: If an unsupported agent type is specified
    #     """
    #     with tracer.start_as_current_span("chat") as span:
    #         span.set_attribute("session_id", session_id)
    #         span.set_attribute("agent_id", agent.id)
    #         span.set_attribute("user_input_length", len(user_input))
            
    #         # Create kernel for this request
    #         kernel = await KernelFactory.create_kernel(agent, session_id=session_id)

    #         #kernel_settings = kernel.get_prompt_execution_settings_from_service_id(service_id=agent.id)
    #         kernel_settings = PromptExecutionSettings(function_choice_behavior=FunctionChoiceBehavior.Auto())

    #         # Try to load existing thread first
    #         existing_thread = await self.thread_storage.load(session_id)

        
    #         # Select the appropriate agent type based on agent properties
    #         if agent.agentType == "AzureAIAgent":
    #             ai_agent, thread = await self._create_azure_ai_agent(kernel, agent, kernel_settings)
    #             # Use existing thread if available
    #             if existing_thread and isinstance(existing_thread, AzureAIAgentThread):
    #                 thread = existing_thread
    #         elif agent.agentType == "ChatCompletionAgent":
    #             ai_agent, thread = await self._create_chat_completion_agent(kernel, agent, kernel_settings)
    #             # Use existing thread if available
    #             if existing_thread and isinstance(existing_thread, ChatHistoryAgentThread):
    #                 thread = existing_thread
    #         else:
    #             raise ValueError(f"Unsupported agent type: {agent.agentType}")
        
    #         try:
    #             # Execute chat completion using the agent's invoke method
    #             with tracer.start_as_current_span("execute_invoke_stream") as completion_span:
    #                 completion_span.set_attribute("provider", agent.modelSelection.provider)
    #                 completion_span.set_attribute("model", agent.modelSelection.model)
    #                 completion_span.set_attribute("agent_type", agent.agentType) 

    #                 # # Generate the streamed agent response(s)
    #                 async for response in ai_agent.invoke_stream(
    #                     messages=user_input, 
    #                     thread=thread
    #                 ):

    #                     # Process the response and yield results
    #                     async for chunk in self._process_function_call_updates(session_id):
    #                         yield chunk
                        
    #                     # Update thread with the latest response
    #                     thread = response.thread

    #                     # Process the normal response content
    #                     yield response.content
                
    #                 # Process any final function calls and clean up
    #                 async for chunk in self._process_final_function_calls(session_id):
    #                     yield chunk
                          
    #                 # Persist the thread to storage
    #                 if thread is not None:
    #                     await self.thread_storage.save(session_id, thread)
    #                     logger.info(f"Persisted thread for session {session_id}")
                    
    #                 logger.info(f"Chat completed successfully for session {session_id} with agent {agent.id}")
                    
    #         except Exception as e:
    #             # Log the error
    #             logger.error(f"Semantic Kernel error in chat: {str(e)}", exc_info=True)
    #             # Set error attributes on span
    #             span.record_exception(e)
    #             span.set_attribute("error", str(e))

    #             # Yield a structured error response that the chat route can identify
    #             yield {"error": f"Error when invoking stream: {str(e)}"}
            

    async def _process_function_call_updates(self, session_id: str) -> AsyncGenerator[str, None]:
        """Process a streaming response chunk, including any pending function calls."""
        # First check the queue for any function calls
        if session_id in function_call_queues:
            while function_call_queues[session_id]:
                call_info = function_call_queues[session_id].popleft()
                icon = "🔄" if call_info["type"] == "function_start" else "✅"
                yield f"{icon} {call_info['function']}\n\n"



    async def _process_final_function_calls(self, session_id: str) -> AsyncGenerator[str, None]:
        """Process any remaining function calls and clean up the queue."""
        # Check for any final function calls
        if session_id in function_call_queues:
            while function_call_queues[session_id]:
                call_info = function_call_queues[session_id].popleft()
                icon = "🔄" if call_info["type"] == "function_start" else "✅"
                yield f"{icon} {call_info['function']}\n\n"
            
            # Clean up
            del function_call_queues[session_id]
    


    # async def _create_chat_completion_agent(self, kernel: Kernel, agent: Agent, kernel_settings) -> tuple[ChatCompletionAgent, ChatHistoryAgentThread]:
    #     """Create a ChatCompletionAgent and its thread."""

    #     # Initialize chat_agent
    #     chat_agent = None
    #     mcp_plugin = None
        
    #     try:
    #         # Create the MCP plugin instance
    #         mcp_plugin = MCPStdioPlugin(
    #             name="Playwright",
    #             description="Playwright plugin for web automation",
    #             command="npx",
    #             args=["@playwright/mcp@latest", "--headless"]
    #         )
            
    #         # Explicitly connect to the MCP server
    #         logger.info("Connecting to Playwright MCP server...")
    #         await mcp_plugin.connect()
            
    #         logger.info("Successfully connected to Playwright MCP server")
            
    #         # Create agent with the connected plugin
    #         chat_agent = ChatCompletionAgent(
    #             kernel=kernel,
    #             name=agent.id,
    #             instructions=agent.systemPrompt,
    #             arguments=KernelArguments(settings=kernel_settings),
    #             plugins=[mcp_plugin]
    #         )
            
    #         # Store the plugin reference to prevent garbage collection
    #         self._mcp_plugin = mcp_plugin
            
    #     except Exception as e:
    #         logger.error(f"Failed to initialize Playwright MCP plugin: {str(e)}", exc_info=True)
            
    #         # If we have a plugin instance that might have connected, try to disconnect it
    #         if mcp_plugin:
    #             try:
    #                 await mcp_plugin.disconnect()
    #             except Exception as disconnect_error:
    #                 logger.warning(f"Error disconnecting MCP plugin: {str(disconnect_error)}")
            
    #         # Fallback to creating agent without plugin
    #         logger.info("Creating agent without MCP plugin")
    #         chat_agent = ChatCompletionAgent(
    #             kernel=kernel,
    #             name=agent.id,
    #             instructions=agent.systemPrompt,
    #             arguments=KernelArguments(settings=kernel_settings),
    #             plugins=[]
    #         )
        
    #     # Create a thread object to maintain the conversation state
    #     thread: ChatHistoryAgentThread = None
        
    #     return chat_agent, thread


    async def _create_chat_completion_agent(self, kernel: Kernel, agent: Agent, kernel_settings) -> tuple[ChatCompletionAgent, ChatHistoryAgentThread]:
        """Create a ChatCompletionAgent and its thread with dynamic MCP tools."""
        
        # Extract MCP tools configuration from agent
        mcp_config = {}
        cleanup_error = None
        
        for tool in agent.tools:
            if tool.type == "ModelContextProtocol" and tool.mcpDefinition:
                # Parse MCP definition
                if isinstance(tool.mcpDefinition, str):
                    tool_config = create_mcp_config_from_json(tool.mcpDefinition)
                else:
                    tool_config = create_mcp_config_from_json(json.dumps(tool.mcpDefinition))
                
                # Add to our plugins configuration
                mcp_config.update(tool_config)
        
        # Clean up any previous plugin manager
        if hasattr(self, '_plugin_manager') and self._plugin_manager is not None:
            try:
                logger.info("Cleaning up previous MCP plugin manager before creating a new one")
                await self._plugin_manager.__aexit__(None, None, None)
            except Exception as e:
                cleanup_error = e
                logger.warning(f"Error during plugin cleanup: {str(e)}")
            finally:
                self._plugin_manager = None
                
        # Create agent with appropriate plugins
        chat_agent = None
        
        # Only initialize MCP plugins if we have configuration for them
        if mcp_config:
            try:
                # Create plugin manager and initialize plugins
                plugin_manager = MCPPluginManager(mcp_config)
                
                # Log warning about previous cleanup if there was one
                if cleanup_error:
                    plugin_manager.warnings.append(f"⚠️ Previous plugin cleanup had an error: {str(cleanup_error)}")
                    
                await plugin_manager.__aenter__()
                
                # Log any warnings
                if plugin_manager.warnings:
                    for warning in plugin_manager.warnings:
                        logger.warning(f"MCP Plugin Warning: {warning}")
                
                # Create agent with the plugins
                chat_agent = ChatCompletionAgent(
                    kernel=kernel,
                    name=agent.id,
                    instructions=agent.systemPrompt,
                    arguments=KernelArguments(settings=kernel_settings),
                    plugins=plugin_manager.plugins
                )
                
                # Store for cleanup
                self._plugin_manager = plugin_manager
                
            except Exception as e:
                logger.error(f"Failed to initialize MCP plugins: {str(e)}", exc_info=True)
                
                # Attempt to clean up the plugin manager if it was created
                if 'plugin_manager' in locals() and plugin_manager is not None:
                    try:
                        await plugin_manager.__aexit__(None, None, None)
                    except Exception as cleanup_error:
                        logger.warning(f"Error cleaning up plugin manager after initialization failure: {str(cleanup_error)}")
                
                # Fall back to agent without plugins
                chat_agent = ChatCompletionAgent(
                    kernel=kernel,
                    name=agent.id,
                    instructions=agent.systemPrompt,
                    arguments=KernelArguments(settings=kernel_settings),
                    plugins=[]
                )
        else:
            # Create agent without plugins
            chat_agent = ChatCompletionAgent(
                kernel=kernel,
                name=agent.id,
                instructions=agent.systemPrompt,
                arguments=KernelArguments(settings=kernel_settings),
                plugins=[]
            )
        
        # Create a thread object to maintain the conversation state
        thread: ChatHistoryAgentThread = None
        
        return chat_agent, thread

    async def _create_azure_ai_agent(self, kernel: Kernel, agent: Agent, kernel_settings) -> tuple[AzureAIAgent, AzureAIAgentThread]:
        """Create an AzureAIAgent and its thread.
        
        **Note:** AzureAIAgent only supports certain models and regions
        Review the following documentation for more details:
        https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/model-region-support
        
        """

        if plugins is None:
            plugins = []

        ai_agent_settings = AzureAIAgentSettings.create()

        creds = DefaultAzureCredential()

        client = AzureAIAgent.create_client(credential=creds)

        # Check if foundryAgentId is provided
        if hasattr(agent, 'foundryAgentId') and agent.foundryAgentId:
            try:
                # Try to get existing agent
                agent_definition = await client.agents.get_agent(agent_id=agent.foundryAgentId)
                # Log successful retrieval
                print(f"Retrieved existing agent with ID: {agent.foundryAgentId}")
            except Exception as e:
                # If retrieval fails, create a new agent
                print(f"Failed to retrieve agent with ID {agent.foundryAgentId}: {str(e)}")
                agent_definition = await client.agents.create_agent(
                    model=ai_agent_settings.model_deployment_name,
                    name=agent.id,
                    instructions=agent.systemPrompt
                )
                print(f"Created new agent with ID: {agent_definition.id}")
        else:
            # No foundryAgentId provided, create a new agent
            agent_definition = await client.agents.create_agent(
                model=ai_agent_settings.model_deployment_name,
                name=agent.id,
                instructions=agent.systemPrompt
            )
            print(f"Created new agent with ID: {agent_definition.id}")

        # Configure AzureAIAgent settings
        # agent_settings = AzureAIAgentSettings(
        #     ai_model_id=agent.modelSelection.model,
        #     instructions=agent.systemPrompt,
        #     # Add other settings as needed
        # )
        
        # Create a Semantic Kernel agent using the Azure AI agent service
        agent = AzureAIAgent(
            arguments=KernelArguments(settings=kernel_settings),
            client=client,
            definition=agent_definition,
            kernel=kernel,
            #name=agent.id,
            #settings=agent_settings,
            plugins=plugins  
            
        )
        
        # Create a thread object for AzureAIAgent
        thread: AzureAIAgentThread = None

        return agent, thread