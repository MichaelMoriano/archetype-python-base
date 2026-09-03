# Repository rules

- Python baseline: 3.13.
- Use uv only; commit `uv.lock`.
- Domain/application must not import FastAPI, HTTPX, Pydantic settings or provider SDKs.
- No security bypass in production code.
- GEN-SECURITY validation success is `returnCode == "000"`; do not decode JWT claims locally.
- Keep business API contracts under `api/v1`; shared middleware/dependencies live under `api/common`.
- Use role suffixes where they improve navigation (`*_router.py`, `*_port.py`, `*_adapter.py`, `*_use_case.py`).
- Group cohesive Pydantic request/response classes in `*_schemas.py`; do not force one file per class.
- Create `api/v2` only when an incompatible external contract is introduced.
