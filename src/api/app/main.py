import logging
from fastapi import FastAPI
from app.routes import chat_router, base_router, liveness_router, readiness_router, startup_router
from app.telemetry import setup_telemetry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI()

# Set up OpenTelemetry with Azure Monitor
tracer = setup_telemetry(app)

# Include routers
app.include_router(base_router)
app.include_router(chat_router, prefix="/api")
app.include_router(liveness_router, prefix="/health")
app.include_router(readiness_router, prefix="/health")
app.include_router(startup_router, prefix="/health")

