import logging

import aiohttp
from fastapi import APIRouter, Response
from opentelemetry import trace

from app.config import get_settings

tracer = trace.get_tracer(__name__)

router = APIRouter()
logger = logging.getLogger(__name__)


@tracer.start_as_current_span(name="startup")
@router.get("/startup")
async def startup_probe(response: Response):
    azure_openai_status_dict = await check_azure_openai()

    return_value = {
        "azure_openai": azure_openai_status_dict,
    }

    response.status_code = 200

    # Set the response status code to 503 if any of the checks failed
    for _, value in return_value.items():
        if value["status"] != 200:
            response.status_code = 503
            break

    return_value["status"] = response.status_code

    logger.info(return_value)

    return return_value


@tracer.start_as_current_span(name="check_azure_openai")
async def check_azure_openai():
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": get_settings().azure_apim_service_subscription_key
    }

    body = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
    }
    async with aiohttp.ClientSession() as session:
        azure_openai_status = await session.post(
            url=(
                f"{get_settings().azure_openai_endpoint}openai/deployments/"
                f"{get_settings().azure_openai_chat_deployment_name}/chat/completions?"
                f"api-version={get_settings().azure_openai_api_version}"
            ),
            json=body,
            headers=headers,
        )

        status_dict = {}

        if azure_openai_status.status == 200:
            status_dict = {"status": 200}
        else:
            status_dict = {
                "status": 503,
                "error": f"Error: {azure_openai_status.status} - {azure_openai_status.reason}",
            }

    return status_dict
