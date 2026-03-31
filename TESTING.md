# Testing Guide

This document describes the comprehensive test suite for the systemic risk metrics project.

## Test Structure

The test suite is organized into three levels:

### 1. Unit Tests (`@pytest.mark.unit`)
- **Fast, isolated tests** with no external dependencies
- Test individual functions and classes in isolation
- Use mocking for external dependencies
- Coverage includes:
  - `src/config.py` - Configuration loading and environment variables
  - `src/universe.py` - Bank registry and lookup functions
  - `src/utils.py` - Utility functions (date validation, etc.)
  - `src/publish.py` - Data publishing functions
  - `src/metrics/` - MES, LRMES, CoVaR, SRISK calculations

### 2. Integration Tests (`@pytest.mark.integration`)
- **Test interactions between components**
- May use mocked external APIs to avoid rate limits
- Coverage includes:
  - `src/fetcher.py` - Data fetching with FX conversion
  - `src/pipeline.py` - Pipeline orchestration and error handling

### 3. End-to-End Tests (`@pytest.mark.e2e`)
- **Complete workflow tests** from data fetch to output
- Test the entire pipeline as users would run it
- Verify data integrity and output format
- Include backfill scenarios

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Levels

```bash
# Unit tests only (fast)
pytest tests/ -m unit

# Integration tests only
pytest tests/ -m integration

# End-to-end tests only (slower)
pytest tests/ -m e2e
```

### Run Tests with Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser

# Generate XML coverage report (for CI)
pytest tests/ --cov=src --cov-report=xml
```

### Run Specific Test Files

```bash
# Test a specific module
pytest tests/test_metrics.py -v

# Test a specific class
pytest tests/test_metrics.py::TestMES -v

# Test a specific function
pytest tests/test_metrics.py::TestMES::test_mes_is_negative -v
```

### Exclude Slow Tests

```bash
pytest tests/ -m "not slow"
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Tests that take >1 second

## Continuous Integration

Tests run automatically on:
- All pushes to `main` branch
- All pull requests
- Manual workflow dispatch

The CI workflow:
1. Runs on Python 3.11 and 3.12
2. Executes unit tests first
3. Runs integration tests if unit tests pass
4. Executes E2E tests in a separate job
5. Generates and uploads coverage reports to Codecov

## Writing New Tests

### Test File Structure

```python
"""tests/test_module.py — Description of what is tested"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.module import function_to_test


@pytest.mark.unit  # or integration, e2e
class TestFeatureName:
    """Tests for specific feature."""

    def test_expected_behavior(self):
        """Test description."""
        result = function_to_test()
        assert result == expected_value
```

### Best Practices

1. **Use descriptive test names** - Test names should describe what is being tested
2. **One assertion per test** - Or multiple related assertions
3. **Use fixtures** - For shared test data (see `tests/conftest.py`)
4. **Mock external dependencies** - Don't make real API calls in unit tests
5. **Test edge cases** - Include tests for error conditions and boundary values
6. **Keep tests fast** - Mark slow tests with `@pytest.mark.slow`

### Common Fixtures

Available fixtures (defined in `tests/conftest.py`):

- `sample_bank_data` - Sample bank metrics for testing
- `temp_data_dir` - Temporary directory for file operations

## Test Coverage Goals

Target coverage by module:

- **Core metrics** (`src/metrics/`): >95%
- **Data pipeline** (`src/pipeline.py`, `src/fetcher.py`): >85%
- **Publishing** (`src/publish.py`): >90%
- **Configuration** (`src/config.py`, `src/universe.py`, `src/utils.py`): >95%

## Existing Test Files

- `tests/test_config.py` - Configuration module tests
- `tests/test_universe.py` - Bank registry tests
- `tests/test_utils.py` - Utility function tests
- `tests/test_publish.py` - Data publishing tests
- `tests/test_metrics.py` - MES, LRMES, CoVaR, SRISK tests
- `tests/test_fetcher.py` - Data fetching and FX conversion tests
- `tests/test_pipeline.py` - Pipeline orchestration tests
- `tests/test_methodology.py` - Methodology documentation consistency tests
- `tests/test_security.py` - Security validation tests
- `tests/test_e2e.py` - End-to-end workflow tests

## Troubleshooting

### Tests fail with import errors

Make sure you've installed all dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Tests fail with "module 'mcp' not found"

The MCP server tests avoid importing the `mcp.server` module to prevent conflicts. If you see this error, check that tests are reading files instead of importing modules where needed.

### Coverage is lower than expected

Run with `--cov-report=term-missing` to see which lines aren't covered:
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
