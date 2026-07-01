import pytest
from pathlib import Path

from gpu_log_analyzer.generator import generate_fixtures

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def test_fixtures():
    """Generate all synthetic fixture files once per test session."""
    generate_fixtures(FIXTURE_DIR)
    return FIXTURE_DIR
