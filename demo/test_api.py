#!/usr/bin/env python3
"""Quick API testing script."""

import requests
import json
import sys
import time


def test_api():
    """Test the API endpoints."""
    base_url = "http://localhost:8000"

    print("Testing AI Chatbot System API")
    print("-" * 40)

    tests = [
        ("Health Check", "/health"),
        ("Root Endpoint", "/"),
        ("API Docs", "/docs"),
        ("Models List", "/api/v1/models"),
    ]

    all_passed = True
    passed = 0
    failed = 0

    for name, endpoint in tests:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"[PASS] {name}")
                passed += 1
                if endpoint == "/health":
                    data = response.json()
                    print(f"       Status: {data.get('status', 'unknown')}")
            else:
                print(f"[FAIL] {name} - Status: {response.status_code}")
                failed += 1
                all_passed = False
        except requests.exceptions.ConnectionError:
            print(f"[FAIL] {name} - Connection failed")
            print("       Is the server running? Start with:")
            print("       python src/chatbot_ai_system/server/main.py")
            failed += 1
            all_passed = False
        except Exception as e:
            print(f"[FAIL] {name} - Error: {str(e)[:50]}")
            failed += 1
            all_passed = False

    print("-" * 40)
    print(f"Results: {passed} passed, {failed} failed")

    if all_passed:
        print("All API tests passed!")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(test_api())
