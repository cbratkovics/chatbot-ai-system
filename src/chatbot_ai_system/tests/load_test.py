from locust import HttpUser, between, task


class ChatbotUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Create a session
        response = self.client.post("/api/v1/chat/sessions")
        self.session_id = response.json()["session_id"]

    @task(3)
    def send_message(self):
        self.client.post(
            "/api/v1/chat/messages",
            json={"message": "Tell me a fun fact", "session_id": self.session_id},
        )

    @task(1)
    def get_health(self):
        self.client.get("/api/v1/health")
