"""Load testing configuration for AI Chatbot System"""

import random

from locust import HttpUser, between, task


class ChatbotUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        # You can add authentication here if needed
        pass

    @task(3)
    def health_check(self):
        """Check health endpoint"""
        self.client.get("/health")

    @task(2)
    def get_docs(self):
        """Access API documentation"""
        self.client.get("/docs")

    @task(5)
    def chat_interaction(self):
        """Simulate chat interaction"""
        messages = [
            "Hello, how are you?",
            "What's the weather like?",
            "Can you help me with a task?",
            "Tell me a joke",
            "What can you do?",
        ]

        payload = {
            "message": random.choice(messages),
            "session_id": f"test-session-{random.randint(1, 1000)}",
        }

        headers = {"Content-Type": "application/json"}

        # Make a POST request to chat endpoint
        with self.client.post(
            "/api/chat", json=payload, headers=headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)
    def get_metrics(self):
        """Get metrics endpoint if available"""
        self.client.get("/metrics", name="/metrics")


class AdminUser(HttpUser):
    """Simulate admin user behavior"""

    wait_time = between(2, 5)
    weight = 1  # Less admin users than regular users

    @task
    def admin_dashboard(self):
        """Access admin endpoints"""
        self.client.get("/admin/dashboard", name="/admin/dashboard")

    @task
    def view_logs(self):
        """View system logs"""
        self.client.get("/admin/logs", name="/admin/logs")
