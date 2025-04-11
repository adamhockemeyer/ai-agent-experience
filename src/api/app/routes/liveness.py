from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/liveness")
async def liveness_probe(response: Response):
    response.status_code = 200
    return {"status": "Ready"}
