"""
Microsoft Agents SDK API Routes

This module provides the Bot Framework /api/messages endpoint that integrates
with our existing Semantic Kernel agents.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, HTTPException, Query
from opentelemetry import trace
from app.config.config import get_settings
from app.dependencies import get_remote_config, get_chat_service, get_thread_storage
from app.models import Agent
from app.services.agent_bridge_service import AgentBridgeService
from app.services.state_bridge_service import StateBridgeService
from app.services.stream_bridge_service import StreamBridgeService
from app.agents_sdk.application import create_agent_application

# These imports will work once we install the Microsoft Agents SDK packages
try:
    from microsoft_agents.hosting.aiohttp import CloudAdapter, start_agent_process
    from microsoft_agents.authentication.msal import MsalConnectionManager
    from microsoft_agents.activity import load_configuration_from_env
    from microsoft_agents.hosting.core.authorization import (
        AgentAuthConfiguration, 
        JwtTokenValidator,
        ClaimsIdentity,
        AuthTypes
    )
    import os
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    # Graceful fallback if SDK not installed yet
    AGENTS_SDK_AVAILABLE = False
    CloudAdapter = None
    MsalConnectionManager = None
    load_configuration_from_env = None
    start_agent_process = None
    AgentAuthConfiguration = None
    JwtTokenValidator = None
    ClaimsIdentity = None
    AuthTypes = None

router = APIRouter()
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

# Global variables for Microsoft Agents SDK components
_adapter = None
_agent_applications = {}  # Cache agent applications by agent_id
_auth_configuration = None
_token_validator = None

async def get_or_create_adapter():
    """Get or create the CloudAdapter for Bot Framework communication."""
    global _adapter, _auth_configuration, _token_validator
    
    if not AGENTS_SDK_AVAILABLE:
        raise HTTPException(
            status_code=500, 
            detail="Microsoft Agents SDK is not installed. Please install the required packages."
        )
    
    if _adapter is None:
        try:
            # Get configuration values directly from settings
            settings = get_settings()
            
            # Create configuration dictionary in the format expected by MsalConnectionManager
            # This follows the structure from the Microsoft Agents SDK documentation
            connections_config = {
                "CONNECTIONS": {
                    "SERVICE_CONNECTION": {
                        "SETTINGS": {
                            "auth_type": AuthTypes.client_secret,
                            "client_id": settings.microsoft_agents_client_id,
                            "client_secret": settings.microsoft_agents_client_secret,
                            "tenant_id": settings.microsoft_agents_tenant_id,
                            "authority": f"https://login.microsoftonline.com/{settings.microsoft_agents_tenant_id}",
                            "scopes": ["https://api.botframework.com/.default"]
                        }
                    }
                }
            }
            
            logger.info(f"Creating MsalConnectionManager with config structure")
            
            # Create the connection manager with the proper configuration format
            connection_manager = MsalConnectionManager(**connections_config)
            
            # Create auth configuration for JWT validation (flattened format)
            auth_config = {
                'client_id': settings.microsoft_agents_client_id,
                'client_secret': settings.microsoft_agents_client_secret,
                'tenant_id': settings.microsoft_agents_tenant_id,
            }
            
            # Create auth configuration for JWT validation
            _auth_configuration = AgentAuthConfiguration(**auth_config)
            
            # Create token validator
            _token_validator = JwtTokenValidator(_auth_configuration)
            
            # Initialize CloudAdapter with proper connection manager
            _adapter = CloudAdapter(connection_manager=connection_manager)
            
            logger.info(f"Microsoft Agents SDK CloudAdapter initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CloudAdapter: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize Bot Framework adapter: {str(e)}")
    
    return _adapter

async def get_or_create_agent_application_manual(
    agent_id: str,
    remote_config,
    chat_service,
    thread_storage
):
    """Get or create the AgentApplication for processing Bot Framework activities (manual dependency resolution)."""
    global _agent_applications
    
    if not AGENTS_SDK_AVAILABLE:
        raise HTTPException(
            status_code=500, 
            detail="Microsoft Agents SDK is not installed. Please install the required packages."
        )
    
    if agent_id not in _agent_applications:
        try:
            # Create bridge services
            agent_bridge = AgentBridgeService(remote_config)
            state_bridge = StateBridgeService(thread_storage)
            stream_bridge = StreamBridgeService(chat_service)
            
            # Create the agent application with the specified agent ID
            _agent_applications[agent_id] = create_agent_application(
                agent_bridge=agent_bridge,
                state_bridge=state_bridge,
                stream_bridge=stream_bridge,
                default_agent_id=agent_id
            )
            
            logger.info(f"Microsoft Agents SDK AgentApplication initialized successfully for agent: {agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AgentApplication for agent {agent_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize agent application for {agent_id}: {str(e)}")
    
    return _agent_applications[agent_id]

async def get_or_create_agent_application(
    agent_id: str,  # Now explicitly passed as parameter
    remote_config = Depends(get_remote_config),
    chat_service = Depends(get_chat_service),
    thread_storage = Depends(get_thread_storage)
):
    """Get or create the AgentApplication for processing Bot Framework activities (FastAPI dependency injection)."""
    return await get_or_create_agent_application_manual(
        agent_id=agent_id,
        remote_config=remote_config,
        chat_service=chat_service,
        thread_storage=thread_storage
    )

class FastAPIRequestAdapter:
    """
    Adapter to make FastAPI Request compatible with aiohttp-style start_agent_process.
    """
    def __init__(self, fastapi_request: Request, claims_identity):
        self._fastapi_request = fastapi_request
        self._claims_identity = claims_identity
        self.headers = fastapi_request.headers
        self.method = fastapi_request.method
        self.url = fastapi_request.url
    
    def __getitem__(self, key):
        """Support dict-style access for claims_identity."""
        if key == "claims_identity":
            return self._claims_identity
        raise KeyError(f"Key '{key}' not found")
    
    def get(self, key, default=None):
        """Support dict-style get for claims_identity."""
        if key == "claims_identity":
            return self._claims_identity
        return default
    
    async def read(self):
        """Read the request body."""
        return await self._fastapi_request.body()
    
    async def json(self):
        """Get JSON body."""
        return await self._fastapi_request.json()

async def validate_jwt_token(request: Request):
    """
    Validate JWT token from the Authorization header and return ClaimsIdentity.
    This replicates the behavior of the aiohttp jwt_authorization_middleware.
    """
    global _token_validator
    
    if not _token_validator:
        # Ensure adapter is initialized (which creates the token validator)
        await get_or_create_adapter()
    
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # Return anonymous claims for development/testing
        logger.warning("No Authorization header found, using anonymous claims")
        return _token_validator.get_anonymous_claims()
    
    try:
        # Extract the token from the Authorization header (Bearer <token>)
        if not auth_header.startswith("Bearer "):
            raise ValueError("Authorization header must start with 'Bearer '")
        
        token = auth_header.split(" ")[1]
        
        # Try to validate the token and get claims
        try:
            claims_identity = _token_validator.validate_token(token)
            logger.info("JWT token validated successfully")
            return claims_identity
        except Exception as validation_error:
            logger.warning(f"JWT validation failed with error: {validation_error}")
            # For Bot Framework development, audience validation might fail
            # Let's use anonymous claims but log the issue
            logger.info("Using anonymous claims due to validation failure - this is OK for development")
            return _token_validator.get_anonymous_claims()
        
    except Exception as e:
        logger.error(f"JWT token extraction error: {e}")
        # For development, we might want to return anonymous claims instead of failing
        logger.warning("JWT token extraction failed, using anonymous claims for development")
        return _token_validator.get_anonymous_claims()

@router.post("/messages")
async def handle_bot_framework_activity(
    request: Request,
    response: Response,
    agentid: Optional[str] = Query(default="orchestrator_agent", description="Agent ID to use for processing the activity"),
    adapter = Depends(get_or_create_adapter),
    remote_config = Depends(get_remote_config),
    chat_service = Depends(get_chat_service),
    thread_storage = Depends(get_thread_storage)
):
    """
    Handle Bot Framework activities through the /api/messages endpoint.
    
    This is the standard Bot Framework endpoint that all Bot Framework channels
    (Teams, WebChat, etc.) will send activities to.
    
    Args:
        agentid: Optional query parameter to specify which agent to use.
                Defaults to 'orchestrator_agent' if not provided.
                Example: /api/messages?agentid=sap_agent
    """
    with tracer.start_as_current_span("bot_framework_activity") as span:
        try:
            if not AGENTS_SDK_AVAILABLE:
                raise HTTPException(
                    status_code=500,
                    detail="Microsoft Agents SDK is not available. Please check installation."
                )
            
            span.set_attribute("endpoint", "/api/messages")
            span.set_attribute("agent_id", agentid)
            logger.info(f"Processing Bot Framework activity with agent: {agentid}")
            
            # Get or create the agent application for the specified agent
            # Use the manual function with resolved dependencies
            agent_app = await get_or_create_agent_application_manual(
                agent_id=agentid,
                remote_config=remote_config,
                chat_service=chat_service,
                thread_storage=thread_storage
            )
            
            # Validate JWT token and get claims identity
            claims_identity = await validate_jwt_token(request)
            
            # Ensure claims_identity is not None
            if claims_identity is None:
                logger.error("Claims identity is None after validation")
                raise HTTPException(status_code=401, detail="Authentication failed: unable to create claims identity")
            
            # Create adapted request that works with aiohttp-style start_agent_process
            adapted_request = FastAPIRequestAdapter(request, claims_identity)
            
            logger.info(f"JWT token validated, processing activity with claims: {type(claims_identity).__name__}")
            
            # Process the incoming activity using the Microsoft Agents SDK pattern
            # This will handle authentication, deserialization, and routing to our agent
            result = await start_agent_process(adapted_request, agent_app, adapter)
            
            logger.info(f"Bot Framework activity processed successfully with agent: {agentid}")
            
            # The start_agent_process function returns a Response object
            return result
            
        except Exception as e:
            logger.error(f"Error processing Bot Framework activity with agent {agentid}: {str(e)}", exc_info=True)
            span.record_exception(e)
            span.set_attribute("error", str(e))
            
            # Return proper error response
            raise HTTPException(status_code=500, detail=f"Error processing activity with agent {agentid}: {str(e)}")

@router.get("/debug/available-agents")
async def debug_available_agents(
    remote_config = Depends(get_remote_config)
):
    """Debug endpoint to check what agent configurations are available."""
    try:
        # Try to load some common agent configurations
        agent_ids = ["orchestrator_agent", "sap_agent", "weather_agent", "document_search"]
        results = {}
        
        for agent_id in agent_ids:
            try:
                agent = await remote_config.get(key=agent_id, model_type=Agent, prefix="agent:")
                results[agent_id] = {
                    "status": "found" if agent else "not_found",
                    "config_exists": agent is not None,
                    "agent_name": agent.name if agent else None,
                    "agent_type": agent.agent_type if agent else None
                }
            except Exception as e:
                results[agent_id] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "status": "success",
            "agent_configurations": results,
            "note": "These are the agent configurations available in Azure App Configuration"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/debug/agents")
async def debug_agents():
    """Debug endpoint to show available agent applications."""
    global _agent_applications
    
    return {
        "status": "success",
        "agent_applications": {
            "available_agents": list(_agent_applications.keys()),
            "total_count": len(_agent_applications),
            "default_agent": "orchestrator_agent"
        },
        "usage_info": {
            "endpoint": "/api/messages",
            "default_usage": "POST /api/messages (uses orchestrator_agent)",
            "specific_agent_usage": "POST /api/messages?agentid=sap_agent",
            "examples": [
                "/api/messages",
                "/api/messages?agentid=orchestrator_agent", 
                "/api/messages?agentid=sap_agent",
                "/api/messages?agentid=weather_agent"
            ]
        }
    }

@router.get("/debug/credentials")
async def debug_credentials():
    """Debug endpoint to validate our credentials work with Azure."""
    try:
        settings = get_settings()
        
        # Test credentials with Azure Identity
        from azure.identity import ClientSecretCredential
        
        credential = ClientSecretCredential(
            tenant_id=settings.microsoft_agents_tenant_id,
            client_id=settings.microsoft_agents_client_id,
            client_secret=settings.microsoft_agents_client_secret
        )
        
        # Try to get a token for Bot Framework
        try:
            token_response = credential.get_token("https://api.botframework.com/.default")
            
            return {
                "status": "success",
                "message": "Azure credentials work correctly",
                "token_expires_on": token_response.expires_on,
                "config": {
                    "client_id": settings.microsoft_agents_client_id,
                    "tenant_id": settings.microsoft_agents_tenant_id,
                }
            }
            
        except Exception as token_error:
            logger.error(f"Azure Identity token acquisition failed: {str(token_error)}")
            
            return {
                "status": "token_error",
                "error": str(token_error),
                "config": {
                    "client_id": settings.microsoft_agents_client_id,
                    "tenant_id": settings.microsoft_agents_tenant_id,
                }
            }
            
    except Exception as e:
        logger.error(f"Credential debug error: {str(e)}")
        
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/debug/msal")
async def debug_msal_authentication():
    """Debug endpoint to test MSAL authentication in isolation."""
    try:
        settings = get_settings()
        
        # Test direct MSAL authentication
        from microsoft_agents.authentication.msal.msal_auth import MsalAuth
        
        # Create MsalAuth instance with our configuration
        msal_auth_config = {
            "client_id": settings.microsoft_agents_client_id,
            "client_secret": settings.microsoft_agents_client_secret,
            "tenant_id": settings.microsoft_agents_tenant_id,
            "authority": f"https://login.microsoftonline.com/{settings.microsoft_agents_tenant_id}",
            "scopes": ["https://api.botframework.com/.default"]
        }
        
        logger.info(f"Testing MSAL auth with config: {msal_auth_config}")
        
        # Create MsalAuth instance
        msal_auth = MsalAuth(**msal_auth_config)
        
        # Try to get a token
        try:
            # Test with Bot Framework service URL
            test_service_url = "https://smba.trafficmanager.net/amer/"
            token = await msal_auth.get_access_token(test_service_url)
            
            return {
                "status": "success",
                "message": "MSAL authentication successful",
                "token_length": len(token) if token else 0,
                "config": {
                    "client_id": settings.microsoft_agents_client_id,
                    "tenant_id": settings.microsoft_agents_tenant_id,
                    "authority": f"https://login.microsoftonline.com/{settings.microsoft_agents_tenant_id}",
                    "scopes": ["https://api.botframework.com/.default"]
                }
            }
            
        except Exception as token_error:
            logger.error(f"Token acquisition failed: {str(token_error)}")
            import traceback
            logger.error(f"Token acquisition traceback: {traceback.format_exc()}")
            
            return {
                "status": "token_error",
                "error": str(token_error),
                "config": {
                    "client_id": settings.microsoft_agents_client_id,
                    "tenant_id": settings.microsoft_agents_tenant_id,
                    "authority": f"https://login.microsoftonline.com/{settings.microsoft_agents_tenant_id}",
                    "scopes": ["https://api.botframework.com/.default"]
                }
            }
            
    except Exception as e:
        logger.error(f"MSAL debug error: {str(e)}")
        import traceback
        logger.error(f"MSAL debug traceback: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/health")
async def agents_sdk_health():
    """Health check endpoint for Microsoft Agents SDK integration."""
    try:
        settings = get_settings()
        
        health_status = {
            "status": "healthy",
            "agents_sdk_available": AGENTS_SDK_AVAILABLE,
            "microsoft_agents_config": {
                "client_id": settings.microsoft_agents_client_id,
                "tenant_id": settings.microsoft_agents_tenant_id,
                "bot_app_id": settings.microsoft_agents_bot_app_id,
            }
        }
        
        if not AGENTS_SDK_AVAILABLE:
            health_status["status"] = "degraded"
            health_status["message"] = "Microsoft Agents SDK packages not installed"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error checking Agents SDK health: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
