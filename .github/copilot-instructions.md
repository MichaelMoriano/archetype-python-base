# Copilot repository instructions

- Baseline: Python 3.13 and `uv`; never create `requirements.txt` or Poetry metadata.
- Keep `uv.lock` versioned and use `uv sync --frozen` in reproducible builds.
- Preserve dependency direction: `domain` <- `application` <- adapters (`api`, `infrastructure`).
- `domain` and `application` must not import FastAPI, HTTPX, Pydantic Settings or provider SDKs.
- FastAPI is an inbound adapter. Keep shared HTTP concerns in `api/common` and versioned contracts in `api/v1`.
- Add `api/v2` only when an incompatible external contract actually exists; do not pre-create empty versions.
- GEN-SECURITY owns JWT validation. Do not decode claims locally. A request proceeds only after `returnCode == "000"`.
- Do not add a production security bypass. Tests must use fakes/dependency replacement.
- External endpoints and secrets must come from Settings/environment; safe operational policies may have defaults.
- Use Protocol ports for external capabilities and implement them in infrastructure.
- Prefer cohesive modules over Java-style one-file-per-class. Use responsibility suffixes (`*_router.py`, `*_port.py`, `*_adapter.py`, `*_use_case.py`) where they aid navigation.
- Never log Authorization headers, tokens, credentials, prompt contents containing sensitive data, or external response bodies containing secrets.
- Do not add RAG, LangChain, LangGraph, Qdrant, LiteLLM or memory to the base archetype unless the service being created needs them.
- New code must pass Ruff, Ruff format, mypy strict, Pytest and coverage.
