"""
State Bridge Service

This service bridges between Bot Framework TurnState and our existing session-based state management.
It handles conversion of Bot Framework conversation references to session IDs and manages state persistence.
"""

import logging
import hashlib
from typing import Dict, Any, Optional
from app.services.thread_storage import ThreadStorage

logger = logging.getLogger(__name__)

class StateBridgeService:
    """Bridges Bot Framework TurnState with our existing session management."""
    
    def __init__(self, thread_storage: ThreadStorage):
        self.thread_storage = thread_storage
        
    def conversation_to_session_id(self, conversation_id: str, user_id: Optional[str] = None) -> str:
        """
        Convert Bot Framework conversation reference to our internal session ID.
        
        Args:
            conversation_id: Bot Framework conversation ID
            user_id: Optional user ID for user-specific sessions
            
        Returns:
            Session ID for our internal systems
        """
        try:
            # Create a deterministic session ID from conversation and user info
            # This ensures the same conversation always maps to the same session
            session_input = f"bf_conv:{conversation_id}"
            if user_id:
                session_input += f":user:{user_id}"
                
            # Use SHA256 to create a consistent session ID
            session_id = hashlib.sha256(session_input.encode()).hexdigest()[:32]
            
            logger.debug(f"Mapped conversation '{conversation_id}' to session '{session_id}'")
            return session_id
            
        except Exception as e:
            logger.error(f"Error converting conversation to session ID: {str(e)}")
            # Fallback to conversation_id if hashing fails
            return conversation_id
    
    async def get_conversation_state(self, conversation_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get conversation state for a Bot Framework conversation.
        
        Args:
            conversation_id: Bot Framework conversation ID
            user_id: Optional user ID
            
        Returns:
            Dictionary containing conversation state
        """
        try:
            session_id = self.conversation_to_session_id(conversation_id, user_id)
            
            # Load existing thread/conversation state
            existing_thread = await self.thread_storage.load(session_id)
            
            state = {
                "session_id": session_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "has_existing_thread": existing_thread is not None
            }
            
            if existing_thread:
                # Extract relevant information from the thread
                if hasattr(existing_thread, '_chat_history') and hasattr(existing_thread._chat_history, 'messages'):
                    state["message_count"] = len(existing_thread._chat_history.messages)
                else:
                    state["message_count"] = 0
                    
                logger.debug(f"Found existing conversation state for session '{session_id}' with {state['message_count']} messages")
            else:
                state["message_count"] = 0
                logger.debug(f"No existing conversation state found for session '{session_id}'")
                
            return state
            
        except Exception as e:
            logger.error(f"Error getting conversation state: {str(e)}")
            # Return minimal state if error occurs
            return {
                "session_id": self.conversation_to_session_id(conversation_id, user_id),
                "conversation_id": conversation_id,
                "user_id": user_id,
                "has_existing_thread": False,
                "message_count": 0
            }
    
    async def save_conversation_state(self, conversation_id: str, state_data: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """
        Save conversation state for a Bot Framework conversation.
        
        Args:
            conversation_id: Bot Framework conversation ID
            state_data: State data to save
            user_id: Optional user ID
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            session_id = self.conversation_to_session_id(conversation_id, user_id)
            
            # Note: The actual thread state is saved by our existing ChatService
            # This method can be used for additional Bot Framework-specific state if needed
            
            logger.debug(f"Conversation state saved for session '{session_id}'")
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversation state: {str(e)}")
            return False
