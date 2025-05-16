from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_ai_api_key: str = ""
    azure_ai_endpoint: str
    azure_application_insights_connection_string: str = ""
    azure_app_config_endpoint: str 
    azure_app_config_connection_string: str = ""
    azure_tracing_gen_ai_content_recording_enabled: bool = False
    semantickernel_experimental_genai_enable_otel_diagnostics_sensitive: bool = False

    # AI Foundry
    azure_ai_agent_project_connection_string: str = ""
    
    # Thread storage configuration
    thread_storage_type: str = "memory"  # Options: "memory", "redis", "cosmosdb"
    redis_connection_string: str = ""
    cosmos_db_connection_string: str = ""
    cosmos_db_endpoint: str = ""
    cosmos_db_database_name: str = "aiagents-db"
    cosmos_db_container_name: str = "chatHistory"
    cosmos_db_partition_key: str = "partitionKey"  # Add this line for the partition key name
    thread_ttl_seconds: int = 86400  # 24 hours default TTL

    # MCP plugin configuration
    mcp_enable_plugins: bool = True
    mcp_timeout_seconds: int = 30
    mcp_max_retries: int = 2
    mcp_npm_registry: str = ""  # Optional custom npm registry
    
    # OpenAPI plugin cache configuration
    openapi_cache_enabled: bool = True
    openapi_cache_ttl_seconds: int = 90  # 1 hour default TTL
    openapi_cache_refresh_interval_seconds: int = 300  # 5 minutes default refresh interval

    model_config = ConfigDict(
        env_file=".env",
        extra="allow"  # Allow extra fields not defined in the model
    )

def get_settings():
    return Settings()
