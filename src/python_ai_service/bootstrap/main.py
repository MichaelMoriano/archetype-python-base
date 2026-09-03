"""FastAPI application factory. Run with Uvicorn --factory."""

from fastapi import FastAPI

from python_ai_service import __version__
from python_ai_service.api.common.constants import API_V1_PREFIX
from python_ai_service.api.common.exception_handlers import register_exception_handlers
from python_ai_service.api.common.middleware.access_log_middleware import add_access_log_middleware
from python_ai_service.api.common.middleware.request_id_middleware import add_request_id_middleware
from python_ai_service.api.v1.api_router import router as v1_router
from python_ai_service.bootstrap.lifespan import build_lifespan
from python_ai_service.config.logging import configure_logging
from python_ai_service.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    application = FastAPI(
        title=resolved.app_name,
        description="Base empresarial para microservicios Python especializados en IA.",
        version=__version__,
        lifespan=build_lifespan(resolved),
    )
    application.state.settings = resolved
    # Starlette executes the last registered middleware as the outer layer.
    add_access_log_middleware(application)
    add_request_id_middleware(application)
    register_exception_handlers(application)
    application.include_router(v1_router, prefix=API_V1_PREFIX)
    return application
