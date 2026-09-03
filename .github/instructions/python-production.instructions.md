---
applyTo: "src/**/*.py"
---
- Use strict type annotations and explicit controlled exceptions.
- Keep composition and resource lifecycle under `bootstrap/`.
- Reuse shared HTTP clients created in lifespan; do not create one client per request.
- Keep provider DTOs and protocol constants inside their adapter context.
- Do not leak infrastructure types through application ports.
