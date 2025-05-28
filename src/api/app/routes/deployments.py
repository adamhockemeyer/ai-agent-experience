from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import HttpResponseError
import logging
from app.config.config import Settings

router = APIRouter()

@router.get("/deployments", response_class=JSONResponse)
def list_deployments():
    """
    List all AI model deployments in the Azure AI Foundry project.
    """
    try:
        settings = Settings()
        endpoint = settings.azure_ai_agent_endpoint
        if not endpoint:
            raise HTTPException(status_code=500, detail="AZURE_AI_AGENT_ENDPOINT config value not set.")
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(credential=credential, endpoint=endpoint)
        deployments = [d for d in project_client.deployments.list()]
        deployments_data = [d.__dict__ for d in deployments]
        return JSONResponse(content=deployments_data)
    except HttpResponseError as e:
        logging.exception(f"Azure error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
