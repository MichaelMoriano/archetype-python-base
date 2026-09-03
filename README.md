# Arquetipo Python Base para Servicios de IA

Base empresarial deliberadamente **sin RAG, LangGraph, Qdrant, LiteLLM ni memoria**.
Su responsabilidad es estandarizar lo que todos los microservicios Python de IA necesitan:

- Python 3.13 + `uv` + `uv.lock` versionado.
- FastAPI con API versionada `/api/v1`.
- `OriginId`, `SubOriginId`, `X-Request-Id`.
- validación JWT remota mediante GEN-SECURITY; el token no se interpreta localmente.
- errores controlados, configuración tipada, logging seguro y lifecycle de clientes HTTP.
- arquitectura hexagonal pragmática y composition root en `bootstrap/`.
- Ruff, mypy strict, Pytest y Docker non-root.

## Arranque local

Copia `.env.example` a `.env` y configura un GEN-SECURITY válido. Luego:

```powershell
uv sync
uv run uvicorn python_ai_service.bootstrap.main:create_app --factory --reload
```

Health público:

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

## Dónde agregar una capacidad

- reglas/modelos puros: `domain/`
- casos de uso y puertos: `application/`
- FastAPI: `api/v1/`
- SDKs, HTTP, DB, Qdrant, LiteLLM: `infrastructure/`
- selección de implementaciones: `bootstrap/composition.py`

No se crea una carpeta `v2` vacía. Se añade cuando realmente nace un contrato V2 incompatible; V1 puede convivir durante la migración.
