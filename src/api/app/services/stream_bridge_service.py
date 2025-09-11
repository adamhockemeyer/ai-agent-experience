"""
Stream Bridge Service

This service bridges between our existing streaming responses and Bot Framework streaming.
It handles conversion of our chat service streams to Bot Framework streaming responses.
"""

import logging
import asyncio
from typing import AsyncGenerator, Optional, List
from app.services.chat_service import ChatService
from app.models import Agent, Attachment

logger = logging.getLogger(__name__)

class StreamBridgeService:
    """Bridges our streaming responses with Bot Framework streaming."""
    
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service
        
    async def process_user_message(
        self, 
        session_id: str, 
        agent: Agent, 
        user_input: str, 
        attachments: Optional[List[Attachment]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message and return streaming response compatible with Bot Framework.
        
        This method leverages our existing ChatService but formats the output
        for Bot Framework consumption.
        
        Args:
            session_id: Session identifier
            agent: Agent configuration
            user_input: User's input text
            attachments: Optional file attachments
            
        Yields:
            String chunks of the response
        """
        try:
            logger.info(f"Processing Bot Framework message for session '{session_id}' with agent '{agent.id}'")
            
            # Use our existing chat service to get the streaming response
            async for chunk in self.chat_service.chat(
                session_id=session_id,
                agent=agent,
                user_input=user_input,
                attachments=attachments
            ):
                # The chunk from our chat service is already a string
                # We can pass it through directly to Bot Framework
                yield chunk
                
        except Exception as e:
            logger.error(f"Error processing user message in stream bridge: {str(e)}")
            yield f"I apologize, but I encountered an error while processing your request: {str(e)}"
    
    async def format_response_for_bot_framework(self, response_text: str) -> str:
        """
        Format a response for Bot Framework consumption.
        
        This method can be used to apply Bot Framework-specific formatting
        to responses if needed.
        
        Args:
            response_text: The response text to format
            
        Returns:
            Formatted response text
        """
        try:
            # For Phase 1, we'll pass through the response as-is
            # This can be enhanced later for Bot Framework-specific formatting
            return response_text
            
        except Exception as e:
            logger.error(f"Error formatting response for Bot Framework: {str(e)}")
            return response_text
    
    async def handle_typing_indicator(self, conversation_id: str) -> None:
        """
        Send typing indicator to Bot Framework conversation.
        
        This can be implemented later when we add more sophisticated
        Bot Framework integration.
        
        Args:
            conversation_id: Bot Framework conversation ID
        """
        try:
            # Placeholder for typing indicator implementation
            logger.debug(f"Typing indicator for conversation '{conversation_id}'")
            
        except Exception as e:
            logger.error(f"Error sending typing indicator: {str(e)}")
    
    async def collect_full_response(
        self, 
        session_id: str, 
        agent: Agent, 
        user_input: str, 
        attachments: Optional[List[Attachment]] = None
    ) -> str:
        """
        Collect the full response from our streaming service for non-streaming scenarios.
        
        Args:
            session_id: Session identifier
            agent: Agent configuration
            user_input: User's input text
            attachments: Optional file attachments
            
        Returns:
            Complete response as a single string
        """
        try:
            response_parts = []
            
            async for chunk in self.process_user_message(session_id, agent, user_input, attachments):
                # Convert chunk to string if it's not already
                if hasattr(chunk, 'content'):
                    # This handles StreamingChatMessageContent objects
                    chunk_text = str(chunk.content) if chunk.content else ""
                elif hasattr(chunk, 'text'):
                    # Handle other message content types
                    chunk_text = str(chunk.text) if chunk.text else ""
                else:
                    # Handle plain strings or other types
                    chunk_text = str(chunk) if chunk else ""
                
                if chunk_text:  # Only add non-empty chunks
                    response_parts.append(chunk_text)
            
            full_response = "".join(response_parts)
            logger.debug(f"Collected full response of {len(full_response)} characters for session '{session_id}'")
            
            return full_response
            
        except Exception as e:
            logger.error(f"Error collecting full response: {str(e)}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
