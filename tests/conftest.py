from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SMALL = ROOT / "tests" / "data" / "small"
MEDIUM = ROOT / "fixtures" / "medium"


@pytest.fixture(scope="session")
def small_dir() -> Path:
    if not SMALL.exists():
        pytest.skip("small fixture missing: run scripts/fetch_fixtures.py small")
    return SMALL


@pytest.fixture(scope="session")
def medium_dir() -> Path:
    if not MEDIUM.exists():
        pytest.skip("medium fixture missing: run scripts/fetch_fixtures.py medium")
    return MEDIUM
