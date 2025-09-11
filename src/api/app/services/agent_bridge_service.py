"""
Agent Bridge Service

This service bridges between the Microsoft Agents SDK and our existing Agent configuration system.
It handles translation of Bot Framework conversations to our agent configurations.
"""

import logging
from typing import Optional
from app.models import Agent
from app.config.remote_config import RemoteConfig

logger = logging.getLogger(__name__)

class AgentBridgeService:
    """Bridges Microsoft Agents SDK with our existing Agent configurations."""
    
    def __init__(self, remote_config: RemoteConfig):
        self.remote_config = remote_config
        
    async def get_agent_for_conversation(self, conversation_id: str, default_agent_id: Optional[str] = None) -> Optional[Agent]:
        """
        Get the appropriate agent configuration for a Bot Framework conversation.
        
        For now, we'll use a default agent, but this can be enhanced to support:
        - Agent selection based on conversation context
        - Multiple agents per bot registration
        - Dynamic agent routing
        
        Args:
            conversation_id: Bot Framework conversation identifier
            default_agent_id: Optional default agent ID to use
            
        Returns:
            Agent configuration or None if not found
        """
        try:
            # For Phase 1, we'll use a configurable default agent
            # This can be enhanced later for more sophisticated routing
            agent_id = default_agent_id or "orchestrator_agent"
            
            logger.info(f"Retrieving agent '{agent_id}' for conversation '{conversation_id}'")
            logger.debug(f"Looking for agent configuration with key: 'agent:{agent_id}'")
            
            agent = await self.remote_config.get(key=agent_id, model_type=Agent, prefix="agent:")
            
            if agent is None:
                logger.warning(f"Agent '{agent_id}' not found for conversation '{conversation_id}' - configuration may not exist in Azure App Configuration")
                logger.warning(f"Expected configuration key: 'agent:{agent_id}'")
            else:
                logger.info(f"Successfully loaded agent '{agent_id}' - name: {agent.name}, type: {agent.agentType}")
                
            return agent
            
        except Exception as e:
            logger.error(f"Error retrieving agent for conversation '{conversation_id}': {str(e)}")
            return None
    
    async def validate_agent_for_bot_framework(self, agent: Agent) -> bool:
        """
        Validate that an agent configuration is compatible with Bot Framework.
        
        Args:
            agent: Agent configuration to validate
            
        Returns:
            True if compatible, False otherwise
        """
        try:
            # Basic validation - can be enhanced as needed
            if not agent.id or not agent.systemPrompt:
                logger.warning(f"Agent '{agent.id}' missing required fields for Bot Framework")
                return False
                
            # Check if agent type is supported
            if agent.agentType not in ["ChatCompletionAgent", "AzureAIAgent"]:
                logger.warning(f"Agent type '{agent.agentType}' may not be fully supported in Bot Framework")
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating agent for Bot Framework: {str(e)}")
            return False
