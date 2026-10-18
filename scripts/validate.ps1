$ErrorActionPreference = "Stop"

Write-Host "`n=== uv lock ==="
uv lock --check
if ($LASTEXITCODE -ne 0) { throw "uv lock check failed." }

Write-Host "`n=== Ruff lint ==="
uv run ruff check .
if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed." }

Write-Host "`n=== Ruff format ==="
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed." }

Write-Host "`n=== mypy ==="
uv run mypy
if ($LASTEXITCODE -ne 0) { throw "mypy failed." }

Write-Host "`n=== Pytest + coverage ==="
uv run pytest --cov --cov-report=term-missing --cov-report=xml:coverage.xml
if ($LASTEXITCODE -ne 0) { throw "pytest failed." }

Write-Host "`nAll validations completed successfully."
