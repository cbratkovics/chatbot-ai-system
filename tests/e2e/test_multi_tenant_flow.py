"""End-to-end tests for multi-tenant flow."""

import asyncio
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient


class TestMultiTenantFlow:
    """Test suite for multi-tenant functionality."""

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """Test complete tenant isolation."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            tenant1_data = {
                "name": "Company A",
                "email": "admin@companya.com",
                "password": "SecurePass123!",
                "plan": "enterprise",
            }
            response = await client.post("/api/v1/tenants/register", json=tenant1_data)
            assert response.status_code == 201
            tenant1 = response.json()

            tenant2_data = {
                "name": "Company B",
                "email": "admin@companyb.com",
                "password": "SecurePass456!",
                "plan": "professional",
            }
            response = await client.post("/api/v1/tenants/register", json=tenant2_data)
            assert response.status_code == 201
            tenant2 = response.json()

            tenant1_headers = {
                "Authorization": f"Bearer {tenant1['access_token']}",
                "X-Tenant-ID": tenant1["tenant_id"],
            }

            tenant2_headers = {
                "Authorization": f"Bearer {tenant2['access_token']}",
                "X-Tenant-ID": tenant2["tenant_id"],
            }

            chat1_response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "Tenant 1 message", "model": "gpt-4"},
                headers=tenant1_headers,
            )
            assert chat1_response.status_code == 200
            chat1 = chat1_response.json()

            chat2_response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "Tenant 2 message", "model": "gpt-4"},
                headers=tenant2_headers,
            )
            assert chat2_response.status_code == 200
            chat2 = chat2_response.json()

            history1 = await client.get("/api/v1/chat/history", headers=tenant1_headers)
            assert history1.status_code == 200
            tenant1_chats = history1.json()

            history2 = await client.get("/api/v1/chat/history", headers=tenant2_headers)
            assert history2.status_code == 200
            tenant2_chats = history2.json()

            assert all(chat["tenant_id"] == tenant1["tenant_id"] for chat in tenant1_chats["items"])
            assert all(chat["tenant_id"] == tenant2["tenant_id"] for chat in tenant2_chats["items"])

            cross_access = await client.get(f"/api/v1/chat/{chat1['id']}", headers=tenant2_headers)
            assert cross_access.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_resource_limits(self):
        """Test tenant-specific resource limits."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            basic_tenant = {
                "name": "Basic Company",
                "email": "admin@basic.com",
                "password": "Pass123!",
                "plan": "basic",
            }
            response = await client.post("/api/v1/tenants/register", json=basic_tenant)
            basic = response.json()

            enterprise_tenant = {
                "name": "Enterprise Company",
                "email": "admin@enterprise.com",
                "password": "Pass456!",
                "plan": "enterprise",
            }
            response = await client.post("/api/v1/tenants/register", json=enterprise_tenant)
            enterprise = response.json()

            basic_headers = {
                "Authorization": f"Bearer {basic['access_token']}",
                "X-Tenant-ID": basic["tenant_id"],
            }

            enterprise_headers = {
                "Authorization": f"Bearer {enterprise['access_token']}",
                "X-Tenant-ID": enterprise["tenant_id"],
            }

            basic_requests = 0
            basic_limited = False
            for i in range(200):
                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"message": f"Basic request {i}", "model": "gpt-3.5-turbo"},
                    headers=basic_headers,
                )
                if response.status_code == 429:
                    basic_limited = True
                    basic_requests = i
                    break

            assert basic_limited is True
            assert basic_requests < 150

            enterprise_requests = 0
            enterprise_limited = False
            for i in range(500):
                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"message": f"Enterprise request {i}", "model": "gpt-4"},
                    headers=enterprise_headers,
                )
                if response.status_code == 429:
                    enterprise_limited = True
                    enterprise_requests = i
                    break

            assert enterprise_requests > basic_requests * 2

    @pytest.mark.asyncio
    async def test_tenant_feature_access(self):
        """Test tenant-specific feature access."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            plans = ["basic", "professional", "enterprise"]
            tenants = {}

            for plan in plans:
                tenant_data = {
                    "name": f"{plan.title()} Company",
                    "email": f"admin@{plan}.com",
                    "password": f"Pass{plan}123!",
                    "plan": plan,
                }
                response = await client.post("/api/v1/tenants/register", json=tenant_data)
                tenants[plan] = response.json()

            basic_headers = {
                "Authorization": f"Bearer {tenants['basic']['access_token']}",
                "X-Tenant-ID": tenants["basic"]["tenant_id"],
            }
            response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "Test", "model": "gpt-4"},
                headers=basic_headers,
            )
            assert response.status_code == 403

            response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "Test", "model": "gpt-3.5-turbo"},
                headers=basic_headers,
            )
            assert response.status_code == 200

            enterprise_headers = {
                "Authorization": f"Bearer {tenants['enterprise']['access_token']}",
                "X-Tenant-ID": tenants["enterprise"]["tenant_id"],
            }

            response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "Test", "model": "gpt-4"},
                headers=enterprise_headers,
            )
            assert response.status_code == 200

            response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "Test", "model": "claude-3-opus"},
                headers=enterprise_headers,
            )
            assert response.status_code == 200

            response = await client.post("/api/v1/analytics/advanced", headers=enterprise_headers)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_tenant_billing_cycle(self):
        """Test tenant billing cycle and usage tracking."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            tenant_data = {
                "name": "Billing Test Company",
                "email": "billing@test.com",
                "password": "BillingPass123!",
                "plan": "professional",
            }
            response = await client.post("/api/v1/tenants/register", json=tenant_data)
            tenant = response.json()

            headers = {
                "Authorization": f"Bearer {tenant['access_token']}",
                "X-Tenant-ID": tenant["tenant_id"],
            }

            start_date = datetime.utcnow()

            for day in range(30):
                for _ in range(10):
                    await client.post(
                        "/api/v1/chat/completions",
                        json={"message": f"Day {day} message", "model": "gpt-3.5-turbo"},
                        headers=headers,
                    )

            end_date = datetime.utcnow()

            usage_response = await client.get(
                f"/api/v1/tenants/{tenant['tenant_id']}/usage",
                params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                headers=headers,
            )
            assert usage_response.status_code == 200
            usage = usage_response.json()

            assert usage["total_requests"] == 300
            assert usage["total_tokens"] > 0
            assert "cost_breakdown" in usage

            billing_response = await client.get(
                f"/api/v1/tenants/{tenant['tenant_id']}/billing", headers=headers
            )
            assert billing_response.status_code == 200
            billing = billing_response.json()

            assert billing["current_usage"] > 0
            assert billing["plan"] == "professional"
            assert "next_billing_date" in billing

    @pytest.mark.asyncio
    async def test_tenant_user_management(self):
        """Test tenant user management."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            tenant_data = {
                "name": "Multi User Company",
                "email": "admin@multiuser.com",
                "password": "AdminPass123!",
                "plan": "enterprise",
            }
            response = await client.post("/api/v1/tenants/register", json=tenant_data)
            tenant = response.json()

            admin_headers = {
                "Authorization": f"Bearer {tenant['access_token']}",
                "X-Tenant-ID": tenant["tenant_id"],
            }

            users = []
            for i in range(5):
                user_data = {
                    "email": f"user{i}@multiuser.com",
                    "password": f"UserPass{i}!",
                    "role": "user" if i < 3 else "manager",
                }
                response = await client.post(
                    f"/api/v1/tenants/{tenant['tenant_id']}/users",
                    json=user_data,
                    headers=admin_headers,
                )
                assert response.status_code == 201
                users.append(response.json())

            response = await client.get(
                f"/api/v1/tenants/{tenant['tenant_id']}/users", headers=admin_headers
            )
            assert response.status_code == 200
            all_users = response.json()
            assert len(all_users["users"]) == 6

            user_login = {"username": users[0]["email"], "password": "UserPass0!"}
            response = await client.post("/api/v1/auth/login", json=user_login)
            assert response.status_code == 200
            user_tokens = response.json()

            user_headers = {
                "Authorization": f"Bearer {user_tokens['access_token']}",
                "X-Tenant-ID": tenant["tenant_id"],
            }

            response = await client.post(
                "/api/v1/chat/completions",
                json={"message": "User message", "model": "gpt-3.5-turbo"},
                headers=user_headers,
            )
            assert response.status_code == 200

            response = await client.delete(
                f"/api/v1/tenants/{tenant['tenant_id']}/users/{users[0]['id']}",
                headers=user_headers,
            )
            assert response.status_code == 403

            response = await client.delete(
                f"/api/v1/tenants/{tenant['tenant_id']}/users/{users[0]['id']}",
                headers=admin_headers,
            )
            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_tenant_data_export(self):
        """Test tenant data export functionality."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            tenant_data = {
                "name": "Export Test Company",
                "email": "admin@export.com",
                "password": "ExportPass123!",
                "plan": "enterprise",
            }
            response = await client.post("/api/v1/tenants/register", json=tenant_data)
            tenant = response.json()

            headers = {
                "Authorization": f"Bearer {tenant['access_token']}",
                "X-Tenant-ID": tenant["tenant_id"],
            }

            for i in range(50):
                await client.post(
                    "/api/v1/chat/completions",
                    json={"message": f"Message {i}", "model": "gpt-3.5-turbo"},
                    headers=headers,
                )

            export_request = {
                "format": "json",
                "include": ["chats", "users", "settings"],
                "date_range": {
                    "start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                    "end": datetime.utcnow().isoformat(),
                },
            }

            response = await client.post(
                f"/api/v1/tenants/{tenant['tenant_id']}/export",
                json=export_request,
                headers=headers,
            )
            assert response.status_code == 202
            export_job = response.json()

            await asyncio.sleep(5)

            response = await client.get(
                f"/api/v1/tenants/{tenant['tenant_id']}/exports/{export_job['job_id']}",
                headers=headers,
            )
            assert response.status_code == 200
            export_status = response.json()

            if export_status["status"] == "completed":
                response = await client.get(export_status["download_url"], headers=headers)
                assert response.status_code == 200
                exported_data = response.json()

                assert "chats" in exported_data
                assert "users" in exported_data
                assert "settings" in exported_data
                assert len(exported_data["chats"]) == 50
