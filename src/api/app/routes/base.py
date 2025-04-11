from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def root() -> dict[str, str]:
    return {"message": "AI Agents API"}


