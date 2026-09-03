$ErrorActionPreference = "Stop"
uv run ruff check . --fix
if ($LASTEXITCODE -ne 0) { throw "Ruff check --fix failed." }
uv run ruff format .
if ($LASTEXITCODE -ne 0) { throw "Ruff format failed." }
