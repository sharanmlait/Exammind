import os
import tempfile

# configure BEFORE the app is imported: offline mock LLM + hash embeddings + throwaway storage
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ANSWER_LLM_PROVIDER"] = ""
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="exammind-test-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def demo(client):
    r = client.post("/api/demo/seed")
    assert r.status_code == 200, r.text
    return r.json()["subject_id"]
