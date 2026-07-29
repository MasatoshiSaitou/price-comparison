"""safety-brief-backend の動作確認スクリプト

実行方法:
    $ python test_api.py

前提: uvicorn main:app --host 0.0.0.0 --port 8000 で起動済みであること。
"""

import os

import requests

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

results = []


def run_test(name, func):
    try:
        func()
        print(f"[PASS] {name}")
        results.append(True)
    except AssertionError as exc:
        print(f"[FAIL] {name}: {exc}")
        results.append(False)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {name}: unexpected error: {exc}")
        results.append(False)


def test_health():
    resp = requests.get(f"{BASE_URL}/health", timeout=10)
    print("  status_code:", resp.status_code)
    print("  body:", resp.json())
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_safety_brief_scaffold_assembly():
    payload = {
        "work_description": "足場の組立で高さ5mの作業",
        "facility_type": "建設現場",
    }
    resp = requests.post(f"{BASE_URL}/safety-brief", json=payload, timeout=40)
    print("  status_code:", resp.status_code)
    body = resp.json()
    print("  body:", body)
    assert resp.status_code in (200, 504)
    assert "text" in body
    assert "incident_count" in body
    assert "incidents" in body
    assert body["incident_count"] == len(body["incidents"])


def test_safety_brief_empty_description():
    payload = {"work_description": ""}
    resp = requests.post(f"{BASE_URL}/safety-brief", json=payload, timeout=10)
    print("  status_code:", resp.status_code)
    print("  body:", resp.json())
    assert resp.status_code == 400


if __name__ == "__main__":
    run_test("GET /health", test_health)
    run_test("POST /safety-brief (足場の組立)", test_safety_brief_scaffold_assembly)
    run_test("POST /safety-brief (空の work_description)", test_safety_brief_empty_description)

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests PASSED")
