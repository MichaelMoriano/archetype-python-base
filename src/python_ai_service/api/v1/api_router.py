"""Version 1 route aggregator. Add api/v2 only when the external contract actually diverges."""

from fastapi import APIRouter

from python_ai_service.api.v1.routers.auth_router import router as auth_router
from python_ai_service.api.v1.routers.health_router import router as health_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
