from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def _extract_id(desc: str, marker: str) -> str:
    import re

    m = re.search(marker, desc)
    return m.group(1) if m else ""


def test_task1_and_task2_ids_change_between_resets():
    t1 = []
    t2 = []
    for _ in range(3):
        r1 = client.post("/reset_task", params={"task_id": "task1"}).json()
        t1.append(_extract_id(r1.get("task_description", ""), r"user ID\s+(\d+)"))

        r2 = client.post("/reset_task", params={"task_id": "task2"}).json()
        t2.append(_extract_id(r2.get("task_description", ""), r"order\s+(ORD-[A-Z]{2}\d{4})"))

    assert len(set(t1)) > 1
    assert len(set(t2)) > 1
    assert all(v.startswith("ORD-") for v in t2)
