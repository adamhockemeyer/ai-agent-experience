# Initialize routes package
from app.routes.chat import router as chat_router
from app.routes.base import router as base_router
from app.routes.liveness import router as liveness_router
from app.routes.readiness import router as readiness_router
from app.routes.startup import router as startup_router
from app.routes.deployments import router as deployments_router

# Optional: Create a container for all routers
class Routers:
    def __init__(self):
        self.chat = chat_router
        self.base = base_router
        self.liveness = liveness_router
        self.readiness = readiness_router 
        self.startup = startup_router
        self.deployments = deployments_router

routers = Routers()