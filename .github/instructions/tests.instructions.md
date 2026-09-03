---
applyTo: "tests/**/*.py"
---
- Use Pytest with Arrange/Act/Assert when it improves readability.
- Unit tests must not call real external services.
- Use HTTPX MockTransport for outbound HTTP adapter contracts.
- Do not weaken production security to make tests easier; replace ports or dependencies in tests.
- Avoid `# type: ignore` when a typed test helper can model the same scenario.
