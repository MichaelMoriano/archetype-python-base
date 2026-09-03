"""Lifecycle of shared infrastructure resources."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
from fastapi import FastAPI

from python_ai_service.bootstrap.composition import build_container
from python_ai_service.config.settings import Settings


def build_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(
            connect=settings.gen_security_connect_timeout_seconds,
            read=settings.gen_security_read_timeout_seconds,
            write=settings.gen_security_write_timeout_seconds,
            pool=settings.gen_security_pool_timeout_seconds,
        )
        limits = httpx.Limits(
            max_connections=settings.gen_security_max_connections,
            max_keepalive_connections=settings.gen_security_max_keepalive_connections,
        )
        security_client = httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=False)
        application.state.container = build_container(
            settings=settings,
            security_client=security_client,
        )
        try:
            yield
        finally:
            await security_client.aclose()

    return lifespan
