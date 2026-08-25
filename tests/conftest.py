import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from config import Config
from database.sqlite import init_db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(Config, "SQLITE_PATH", db_path)
    init_db(db_path)
    yield db_path
