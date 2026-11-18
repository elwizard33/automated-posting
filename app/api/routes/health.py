from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def health() -> HealthResponse:
    return HealthResponse()
