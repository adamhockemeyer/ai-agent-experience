from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from opentelemetry.trace import SpanContext, format_trace_id
import json
import logging
from typing import Any
from app.models import ChatRequest, ChatResponse, Agent
from app.services.chat_service import ChatService
from app.config.azure_app_config import AzureAppConfig
from app.dependencies import get_chat_service, get_remote_config

router = APIRouter()
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    chat_service: ChatService = Depends(get_chat_service),
    agent_config: AzureAppConfig = Depends(get_remote_config)
) -> Any:
    """
    Chat with an AI agent with streaming response.
    The response is streamed as server-sent events (SSE).
    """
    with tracer.start_as_current_span("chat_endpoint") as span:
        span.set_attribute("session_id", request.session_id)
        span.set_attribute("agent_id", request.agent_id)

        # Get current span context to extract trace ID
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()
        trace_id = format_trace_id(span_context.trace_id)
        
        # Fetch the agent configuration using agent_id
        try:
            agent = await agent_config.get(key=request.agent_id, model_type=Agent, prefix="agent:")     
        except Exception as e:
            logger.exception(f"Error fetching agent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal server error while fetching agent configuration. {str(e)}")
    
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent with ID '{request.agent_id}' not found")
        
        # Call the chat service to get the streaming response
        async def stream_response():
            try:
                # Get the streaming response from chat service
                async for chunk in chat_service.chat(
                    session_id=request.session_id,
                    agent=agent,
                    user_input=request.input
                ):
                    # # Extract the string content from the StreamingChatMessageContent object
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                    else:
                        content = str(chunk)
                    
                    yield content

            except Exception as e:
                logger.exception(f"Error streaming response: {str(e)}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                # Send error message as an event
                yield f"An unexpected error occurred: {str(e)}"
        
        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-OTel-Trace-ID": trace_id
            }
        )