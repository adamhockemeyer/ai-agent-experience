# app/agents/service_factory.py

import logging
from typing import Optional
from opentelemetry import trace

from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

from app.models import Agent
from app.config import get_settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ServiceFactory:
    """Factory for creating AI service clients based on agent configuration."""
    
    @staticmethod
    def create_service(agent_config: Agent) -> Optional[ChatCompletionClientBase]:
        """
        Create an appropriate AI service based on agent configuration.
        
        Args:
            agent_config: The agent configuration containing model selection information
            
        Returns:
            An initialized service client or None if creation failed
        """
        with tracer.start_as_current_span("create_service") as span:
            if not agent_config.modelSelection:
                logger.error("No model selection provided in agent configuration")
                return None
                
            provider = agent_config.modelSelection.provider
            model = agent_config.modelSelection.model
            
            span.set_attribute("provider", provider)
            span.set_attribute("model", model)
            span.set_attribute("agent_id", agent_config.id)
            
            settings = get_settings()
            
            # Use the provider to determine which service to create
            try:
                if provider == "AzureOpenAI":
                    with tracer.start_as_current_span("create_azure_openai_service"):
                        return AzureChatCompletion(
                            deployment_name=model,
                            endpoint=settings.azure_openai_endpoint,
                            api_key=settings.azure_openai_api_key,
                            service_id=agent_config.id
                        )
                elif provider == "AzureAIInference":
                    with tracer.start_as_current_span("create_azure_ai_inference_service"):
                        return AzureAIInferenceChatCompletion(
                            ai_model_id=model,
                            endpoint=settings.azure_ai_endpoint,
                            api_key=settings.azure_ai_api_key,
                            service_id=agent_config.id
                        )
                else:
                    logger.error(f"Unsupported provider: {provider}")
                    span.set_attribute("error", f"unsupported_provider_{provider}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error creating AI service: {str(e)}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return None