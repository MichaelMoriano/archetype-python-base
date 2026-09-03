from fastapi import APIRouter, Request

from python_ai_service.api.common.schemas.health_schemas import HealthResponse
from python_ai_service.config.settings import Settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", response_model=HealthResponse)
def live(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="alive",
        service=settings.app_name,
        environment=settings.app_environment,
    )


@router.get("/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ready",
        service=settings.app_name,
        environment=settings.app_environment,
    )
