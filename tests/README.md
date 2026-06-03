# Tests

Smoke and contract tests for schemas and core scripts. Run from repository root:

```bash
pip install -r environment/requirements.txt
pytest tests/ -q
```

Tests use inline fixtures only; no large datasets are required.
