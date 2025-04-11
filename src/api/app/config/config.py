from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_ai_api_key: str
    azure_ai_endpoint: str
    azure_application_insights_connection_string: str = ""
    azure_app_config_endpoint: str 
    azure_app_config_connection_string: str = ""
    azure_tracing_gen_ai_content_recording_enabled: bool = False
    semantickernel_experimental_genai_enable_otel_diagnostics_sensitive: bool = False
    
    # Thread storage configuration
    thread_storage_type: str = "memory"  # Options: "memory", "redis", "cosmosdb"
    redis_connection_string: str = ""
    cosmos_db_connection_string: str = ""
    cosmos_db_endpoint: str = ""
    cosmos_db_database_name: str = "ConversationThreads"
    cosmos_db_container_name: str = "Threads"
    cosmos_db_partition_key: str = "sessionId"  # Add this line for the partition key name
    thread_ttl_seconds: int = 86400  # 24 hours default TTL


     # MCP plugin configuration
    mcp_enable_plugins: bool = True
    mcp_timeout_seconds: int = 30
    mcp_max_retries: int = 2
    mcp_npm_registry: str = ""  # Optional custom npm registry

    model_config = ConfigDict(
        env_file=".env",
        extra="allow"  # Allow extra fields not defined in the model
    )

def get_settings():
    return Settings()
