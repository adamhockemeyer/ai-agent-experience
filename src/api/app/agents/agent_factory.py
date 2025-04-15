# app/agents/agent_factory.py
import logging
from typing import Tuple, List, Any, Optional
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread, AzureAIAgent, AzureAIAgentThread
from semantic_kernel.functions import KernelArguments
from azure.identity.aio import DefaultAzureCredential
from opentelemetry import trace

from app.models import Agent
from app.config.config import get_settings
from app.agents.service_factory import ServiceFactory

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class AgentFactory:
    """Factory for creating semantic kernel agents based on configuration."""
    
    @staticmethod
    async def create_agent(kernel: Kernel, agent_config: Agent, plugins: List[Any] = None) -> Tuple[Any, Any]:
        """Create an agent and thread based on the agent configuration."""
        with tracer.start_as_current_span("create_agent") as span:
            span.set_attribute("agent_id", agent_config.id)
            span.set_attribute("agent_type", agent_config.agentType)
            
            if plugins is None:
                plugins = []
                
            kernel_settings = PromptExecutionSettings(
                function_choice_behavior=FunctionChoiceBehavior.Auto()
            )
            
            # Create the appropriate agent type
            if agent_config.agentType == "AzureAIAgent":
                return await AgentFactory._create_azure_ai_agent(
                    kernel, agent_config, kernel_settings, plugins
                )
            else:
                # Default to ChatCompletionAgent
                # Create AI service for the chat completion agent
                service = ServiceFactory.create_service(agent_config)
                if service:
                    # Add service to kernel for other potential users
                    kernel.add_service(service)
                
                return await AgentFactory._create_chat_completion_agent(
                    kernel, agent_config, kernel_settings, plugins, service
                )
    
    @staticmethod
    async def _create_chat_completion_agent(
        kernel: Kernel, 
        agent_config: Agent, 
        kernel_settings: PromptExecutionSettings, 
        plugins: List[Any],
        service = None
    ) -> Tuple[ChatCompletionAgent, Optional[ChatHistoryAgentThread]]:
        """Create a ChatCompletionAgent."""
        
        try:
            # Create agent with the plugins, passing service directly if available
            if service:
                chat_agent = ChatCompletionAgent(
                    kernel=kernel,
                    name=agent_config.id,
                    instructions=agent_config.systemPrompt,
                    arguments=KernelArguments(settings=kernel_settings),
                    plugins=plugins,
                    service=service
                )
            else:
                chat_agent = ChatCompletionAgent(
                    kernel=kernel,
                    name=agent_config.id,
                    instructions=agent_config.systemPrompt,
                    arguments=KernelArguments(settings=kernel_settings),
                    plugins=plugins
                )
            
            # Create a thread object to maintain the conversation state
            thread: ChatHistoryAgentThread = ChatHistoryAgentThread()
            
            return chat_agent, thread
            
        except Exception as e:
            logger.error(f"Error creating ChatCompletionAgent: {str(e)}", exc_info=True)
            raise
        
    @staticmethod
    async def _create_azure_ai_agent(
        kernel: Kernel, 
        agent_config: Agent, 
        kernel_settings: PromptExecutionSettings, 
        plugins: List[Any]
    ) -> Tuple[AzureAIAgent, Optional[AzureAIAgentThread]]:
        """Create an AzureAIAgent."""
        
        try:
            creds = DefaultAzureCredential()
            client = AzureAIAgent.create_client(credential=creds)
            
            # Check if foundryAgentId is provided
            if hasattr(agent_config, 'foundryAgentId') and agent_config.foundryAgentId:
                try:
                    # Try to get existing agent
                    agent_definition = await client.agents.get_agent(agent_id=agent_config.foundryAgentId)
                    logger.info(f"Retrieved existing agent with ID: {agent_config.foundryAgentId}")
                except Exception as e:
                    # If retrieval fails, create a new agent
                    logger.warning(f"Failed to retrieve agent with ID {agent_config.foundryAgentId}: {str(e)}")
                    agent_definition = await client.agents.create_agent(
                        model=agent_config.modelSelection.model,
                        name=agent_config.id,
                        instructions=agent_config.systemPrompt
                    )
                    logger.info(f"Created new agent with ID: {agent_definition.id}")
            else:
                # No foundryAgentId provided, create a new agent
                agent_definition = await client.agents.create_agent(
                    model=agent_config.modelSelection.model,
                    name=agent_config.id,
                    instructions=agent_config.systemPrompt
                )
                logger.info(f"Created new agent with ID: {agent_definition.id}")
            
            # Create a Semantic Kernel agent using the Azure AI agent service
            azure_ai_agent = AzureAIAgent(
                arguments=KernelArguments(settings=kernel_settings),
                client=client,
                definition=agent_definition,
                kernel=kernel,
                plugins=plugins
            )
            
            # Create a thread object for AzureAIAgent
            thread: AzureAIAgentThread = AzureAIAgentThread(client=client)
            
            return azure_ai_agent, thread
            
        except Exception as e:
            logger.error(f"Error creating AzureAIAgent: {str(e)}", exc_info=True)
            raise