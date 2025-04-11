from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/readiness")
async def readiness_probe(response: Response):
    response.status_code = 200
    return {"status": "Ready"}
