"""
Microsoft Agents SDK Application

This module contains the main AgentApplication class that integrates with our existing
Semantic Kernel agents through the bridge services.
"""

import logging
from typing import Optional
from microsoft_agents.hosting.core import (
    AgentApplication, 
    TurnContext, 
    TurnState,
    MessageFactory,
    MemoryStorage
)
from app.services.agent_bridge_service import AgentBridgeService
from app.services.state_bridge_service import StateBridgeService
from app.services.stream_bridge_service import StreamBridgeService

logger = logging.getLogger(__name__)

class SemanticKernelAgentApplication(AgentApplication):
    """
    Microsoft Agents SDK application that bridges to our Semantic Kernel agents.
    """
    
    def __init__(
        self, 
        agent_bridge: AgentBridgeService,
        state_bridge: StateBridgeService,
        stream_bridge: StreamBridgeService,
        default_agent_id: Optional[str] = None
    ):
        """
        Initialize the agent application with bridge services.
        
        Args:
            agent_bridge: Service for bridging agent configurations
            state_bridge: Service for bridging conversation state
            stream_bridge: Service for bridging streaming responses
            default_agent_id: Default agent to use for conversations
        """
        # Initialize with memory storage for now
        super().__init__(storage=MemoryStorage())
        
        self.agent_bridge = agent_bridge
        self.state_bridge = state_bridge
        self.stream_bridge = stream_bridge
        self.default_agent_id = default_agent_id
        
        # Register event handlers
        self._register_handlers()
        
        logger.info("SemanticKernelAgentApplication initialized")
    
    def _register_handlers(self):
        """Register event handlers for Bot Framework activities."""
        
        # Handle when new members are added to conversation
        @self.conversation_update("membersAdded")
        async def on_members_added(context: TurnContext, state: TurnState):
            """Handle members added to conversation."""
            try:
                members_added = context.activity.members_added
                for member in members_added:
                    if member.id != context.activity.recipient.id:
                        welcome_message = "Hello! I'm your AI assistant. How can I help you today?"
                        await context.send_activity(MessageFactory.text(welcome_message))
                        
                        logger.info(f"Welcomed new member to conversation: {context.activity.conversation.id}")
                        
            except Exception as e:
                logger.error(f"Error handling members added: {str(e)}")
                await context.send_activity(MessageFactory.text("Welcome! How can I assist you?"))
        
        # Handle message activities
        @self.activity("message")
        async def on_message(context: TurnContext, state: TurnState):
            """Handle incoming message activities."""
            try:
                user_input = context.activity.text
                if not user_input:
                    await context.send_activity(MessageFactory.text("I didn't receive any text. Please try again."))
                    return
                
                conversation_id = context.activity.conversation.id
                user_id = context.activity.from_property.id if context.activity.from_property else None
                
                logger.info(f"Processing message from conversation '{conversation_id}': {user_input[:100]}...")
                
                # Get agent configuration
                agent = await self.agent_bridge.get_agent_for_conversation(
                    conversation_id, 
                    self.default_agent_id
                )
                
                if not agent:
                    error_message = "I'm sorry, but I'm not configured properly. Please contact support."
                    await context.send_activity(MessageFactory.text(error_message))
                    return
                
                # Validate agent for Bot Framework
                if not await self.agent_bridge.validate_agent_for_bot_framework(agent):
                    error_message = "I'm sorry, but my configuration is invalid. Please contact support."
                    await context.send_activity(MessageFactory.text(error_message))
                    return
                
                # Get conversation state
                conv_state = await self.state_bridge.get_conversation_state(conversation_id, user_id)
                session_id = conv_state["session_id"]
                
                # Send typing indicator (if supported)
                await self.stream_bridge.handle_typing_indicator(conversation_id)
                
                # For Phase 1, we'll collect the full response and send it at once
                # Phase 3 will implement true streaming
                response = await self.stream_bridge.collect_full_response(
                    session_id=session_id,
                    agent=agent,
                    user_input=user_input,
                    attachments=None  # Phase 2 will add attachment support
                )
                
                # Send the response
                await context.send_activity(MessageFactory.text(response))
                
                logger.info(f"Sent response to conversation '{conversation_id}' (length: {len(response)})")
                
            except Exception as e:
                logger.error(f"Error handling message activity: {str(e)}", exc_info=True)
                error_message = "I apologize, but I encountered an error processing your request. Please try again."
                await context.send_activity(MessageFactory.text(error_message))


def create_agent_application(
    agent_bridge: AgentBridgeService,
    state_bridge: StateBridgeService,
    stream_bridge: StreamBridgeService,
    default_agent_id: Optional[str] = None
) -> SemanticKernelAgentApplication:
    """
    Factory function to create the Microsoft Agents SDK application.
    
    Args:
        agent_bridge: Service for bridging agent configurations
        state_bridge: Service for bridging conversation state
        stream_bridge: Service for bridging streaming responses
        default_agent_id: Default agent to use for conversations
        
    Returns:
        Configured SemanticKernelAgentApplication instance
    """
    return SemanticKernelAgentApplication(
        agent_bridge=agent_bridge,
        state_bridge=state_bridge,
        stream_bridge=stream_bridge,
        default_agent_id=default_agent_id
    )
