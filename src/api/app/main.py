import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes import chat_router, base_router, liveness_router, readiness_router, startup_router, deployments_router
from app.telemetry import setup_telemetry
from app.services.openapi_spec_cache import OpenAPISpecCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Define lifespan context manager for application startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    logging.info("Starting application services...")
    
    # Get the OpenAPI spec cache instance
    openapi_cache = OpenAPISpecCache.get_instance()
    
    # Prefetch all OpenAPI specs - wrap in try/except to ensure app starts even if prefetch fails
    try:
        await openapi_cache.prefetch_all_specs()
        logging.info("OpenAPI specs prefetched successfully")
    except Exception as e:
        # Log but continue app startup - the cache will fetch specs on-demand if needed
        logging.error(f"Error prefetching OpenAPI specs: {str(e)}")
        logging.info("Application will continue without prefetched specs")
    
    yield  # Application runs here
    
    # Shutdown: Clean up resources
    logging.info("Shutting down application services...")
    
    # Clean up the OpenAPI spec cache - wrap in try/except to ensure clean shutdown
    try:
        await openapi_cache.cleanup()
        logging.info("OpenAPI spec cache cleaned up")
    except Exception as e:
        logging.error(f"Error cleaning up OpenAPI spec cache: {str(e)}")

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Set up OpenTelemetry with Azure Monitor
tracer = setup_telemetry(app)

# Include routers
app.include_router(base_router)
app.include_router(chat_router, prefix="/api")
app.include_router(deployments_router, prefix="/api")
app.include_router(liveness_router, prefix="/health")
app.include_router(readiness_router, prefix="/health")
app.include_router(startup_router, prefix="/health")

