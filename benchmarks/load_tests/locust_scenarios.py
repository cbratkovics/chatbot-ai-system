"""
Locust scenarios for realistic user behavior testing.
Tests different user personas and usage patterns.
"""

import json
import random
import time
from datetime import datetime, timedelta
from locust import HttpUser, TaskSet, task, between, events
from locust.exception import RescheduleTask
import hashlib
import statistics

# Global metrics storage for custom reporting
metrics_storage = {
    'cache_hits': 0,
    'cache_misses': 0,
    'model_switches': 0,
    'conversation_lengths': [],
    'response_times_by_model': {},
    'token_usage': [],
    'cost_estimates': [],
}

# Test data
MODELS = ['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus', 'claude-3-sonnet', 'llama-3-70b']
TENANTS = ['tenant-1', 'tenant-2', 'tenant-3', 'tenant-4', 'tenant-5']

# Realistic prompts categorized by user type
BEGINNER_PROMPTS = [
    "What is Python?",
    "How do I create a variable?",
    "What is a function?",
    "Explain loops in simple terms",
    "What is an API?",
    "How do I learn programming?",
    "What is a database?",
    "What is version control?",
]

DEVELOPER_PROMPTS = [
    "How do I optimize this SQL query for better performance?",
    "What's the difference between REST and GraphQL?",
    "Explain the Observer pattern with code examples",
    "How do I implement JWT authentication in FastAPI?",
    "What are the best practices for microservices communication?",
    "How do I handle race conditions in concurrent programming?",
    "Explain database sharding strategies",
    "What's the best way to implement caching in a distributed system?",
]

POWER_USER_PROMPTS = [
    "Design a distributed system for real-time analytics with 1M events/sec",
    "Compare different consensus algorithms for distributed systems",
    "Implement a lock-free concurrent data structure",
    "Explain the internals of a B+ tree and its optimization techniques",
    "How would you design a globally distributed database with strong consistency?",
    "What are the trade-offs between different garbage collection algorithms?",
    "Design a system for processing 1PB of data daily",
    "Explain quantum-resistant cryptography algorithms",
]

# Conversation contexts that would trigger caching
CACHEABLE_PROMPTS = [
    "What is machine learning?",
    "Explain Docker containers",
    "What are microservices?",
    "How does OAuth 2.0 work?",
    "What is the CAP theorem?",
]


class UserBehavior(TaskSet):
    """Base user behavior class"""
    
    def on_start(self):
        """Initialize user session"""
        self.tenant_id = random.choice(TENANTS)
        self.user_id = f"user_{self.user.environment.runner.user_count}_{random.randint(1000, 9999)}"
        self.conversation_id = None
        self.message_count = 0
        self.conversation_start = None
        self.selected_model = random.choice(MODELS)
        self.auth_token = self.authenticate()
        
    def authenticate(self):
        """Authenticate and get JWT token"""
        with self.client.post(
            "/api/v1/auth/login",
            json={
                "username": self.user_id,
                "password": "test_password",
                "tenant_id": self.tenant_id,
            },
            catch_response=True,
            name="auth_login"
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json().get("access_token")
            else:
                response.failure(f"Auth failed: {response.status_code}")
                raise RescheduleTask()
    
    def get_headers(self):
        """Get request headers with auth"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "X-Tenant-ID": self.tenant_id,
            "X-User-ID": self.user_id,
            "Content-Type": "application/json",
        }
    
    def create_conversation(self):
        """Create a new conversation"""
        with self.client.post(
            "/api/v1/conversations",
            json={
                "title": f"Conversation {datetime.now().isoformat()}",
                "model": self.selected_model,
                "metadata": {
                    "user_type": self.__class__.__name__,
                    "test_run": True,
                }
            },
            headers=self.get_headers(),
            catch_response=True,
            name="create_conversation"
        ) as response:
            if response.status_code == 201:
                response.success()
                self.conversation_id = response.json().get("id")
                self.conversation_start = time.time()
                self.message_count = 0
            else:
                response.failure(f"Failed to create conversation: {response.status_code}")
    
    def send_message(self, prompt, use_cache_test=False):
        """Send a chat message"""
        if not self.conversation_id:
            self.create_conversation()
        
        # For cache testing, create a deterministic prompt
        if use_cache_test:
            prompt = random.choice(CACHEABLE_PROMPTS)
        
        start_time = time.time()
        
        with self.client.post(
            "/api/v1/chat/completions",
            json={
                "conversation_id": self.conversation_id,
                "message": prompt,
                "model": self.selected_model,
                "parameters": {
                    "temperature": 0.7 if not use_cache_test else 0.0,
                    "max_tokens": 500,
                    "stream": False,
                }
            },
            headers=self.get_headers(),
            catch_response=True,
            name="chat_completion"
        ) as response:
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if response.status_code == 200:
                response.success()
                self.message_count += 1
                
                # Track cache performance
                if response.headers.get("X-Cache-Hit") == "true":
                    metrics_storage['cache_hits'] += 1
                else:
                    metrics_storage['cache_misses'] += 1
                
                # Track model switches
                if response.headers.get("X-Model-Switch") == "true":
                    metrics_storage['model_switches'] += 1
                    actual_model = response.json().get("model", self.selected_model)
                else:
                    actual_model = self.selected_model
                
                # Track response times by model
                if actual_model not in metrics_storage['response_times_by_model']:
                    metrics_storage['response_times_by_model'][actual_model] = []
                metrics_storage['response_times_by_model'][actual_model].append(response_time)
                
                # Track token usage and cost
                usage = response.json().get("usage", {})
                if usage:
                    metrics_storage['token_usage'].append(usage.get("total_tokens", 0))
                    metrics_storage['cost_estimates'].append(usage.get("estimated_cost", 0))
                
            elif response.status_code == 429:
                response.failure("Rate limit exceeded")
            else:
                response.failure(f"Chat failed: {response.status_code}")
    
    def end_conversation(self):
        """End current conversation and track metrics"""
        if self.conversation_id and self.conversation_start:
            duration = time.time() - self.conversation_start
            metrics_storage['conversation_lengths'].append({
                'messages': self.message_count,
                'duration': duration,
                'user_type': self.__class__.__name__,
            })
            self.conversation_id = None
            self.conversation_start = None


class NewUserBehavior(UserBehavior):
    """New user - asks basic questions, short sessions"""
    
    wait_time = between(5, 15)  # Longer think time
    
    @task(10)
    def ask_basic_question(self):
        """Ask a beginner-level question"""
        prompt = random.choice(BEGINNER_PROMPTS)
        self.send_message(prompt)
        
        # New users often end conversations quickly
        if self.message_count >= random.randint(2, 5):
            self.end_conversation()
    
    @task(2)
    def test_different_model(self):
        """New users might try different models"""
        self.selected_model = random.choice(MODELS)
        self.create_conversation()
        self.send_message("Hello, can you help me?")
    
    @task(1)
    def check_usage(self):
        """Check usage statistics"""
        with self.client.get(
            "/api/v1/usage/stats",
            headers=self.get_headers(),
            name="usage_stats"
        ) as response:
            if response.status_code == 200:
                response.success()


class ReturningUserBehavior(UserBehavior):
    """Returning user - moderate usage, longer conversations"""
    
    wait_time = between(3, 8)
    
    @task(15)
    def ask_technical_question(self):
        """Ask developer-level questions"""
        prompt = random.choice(DEVELOPER_PROMPTS)
        self.send_message(prompt)
        
        # Continue conversation
        if self.message_count >= random.randint(5, 15):
            self.end_conversation()
    
    @task(5)
    def use_cached_prompt(self):
        """Test cache effectiveness with common prompts"""
        self.send_message("", use_cache_test=True)
    
    @task(3)
    def get_conversation_history(self):
        """Retrieve conversation history"""
        if self.conversation_id:
            with self.client.get(
                f"/api/v1/conversations/{self.conversation_id}/messages",
                headers=self.get_headers(),
                name="get_history"
            ) as response:
                if response.status_code == 200:
                    response.success()
    
    @task(2)
    def search_semantic(self):
        """Perform semantic search"""
        if self.conversation_id:
            with self.client.post(
                "/api/v1/search/semantic",
                json={
                    "query": random.choice(DEVELOPER_PROMPTS),
                    "conversation_id": self.conversation_id,
                    "limit": 5,
                },
                headers=self.get_headers(),
                name="semantic_search"
            ) as response:
                if response.status_code == 200:
                    response.success()


class PowerUserBehavior(UserBehavior):
    """Power user - heavy usage, complex queries, long sessions"""
    
    wait_time = between(1, 3)  # Minimal think time
    
    @task(20)
    def ask_complex_question(self):
        """Ask advanced technical questions"""
        prompt = random.choice(POWER_USER_PROMPTS)
        self.send_message(prompt)
        
        # Power users have long conversations
        if self.message_count >= random.randint(15, 30):
            self.end_conversation()
    
    @task(10)
    def rapid_fire_questions(self):
        """Send multiple questions quickly"""
        for _ in range(random.randint(3, 7)):
            prompt = random.choice(DEVELOPER_PROMPTS + POWER_USER_PROMPTS)
            self.send_message(prompt)
            time.sleep(random.uniform(0.5, 1.5))
    
    @task(5)
    def test_model_switching(self):
        """Test failover by forcing model switches"""
        models_to_test = random.sample(MODELS, 3)
        for model in models_to_test:
            self.selected_model = model
            prompt = f"Using {model}: {random.choice(POWER_USER_PROMPTS)}"
            self.send_message(prompt)
    
    @task(3)
    def stress_test_cache(self):
        """Repeatedly send same prompts to test cache"""
        prompt = random.choice(CACHEABLE_PROMPTS)
        for _ in range(5):
            self.send_message(prompt, use_cache_test=True)
            time.sleep(0.5)
    
    @task(2)
    def export_conversation(self):
        """Export conversation data"""
        if self.conversation_id:
            with self.client.get(
                f"/api/v1/conversations/{self.conversation_id}/export",
                headers=self.get_headers(),
                name="export_conversation"
            ) as response:
                if response.status_code == 200:
                    response.success()


class MixedUser(HttpUser):
    """Mixed user population simulating realistic distribution"""
    tasks = {
        NewUserBehavior: 30,       # 30% new users
        ReturningUserBehavior: 50,  # 50% returning users
        PowerUserBehavior: 20,       # 20% power users
    }
    
    host = "http://localhost:8000"


# Event handlers for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test metrics"""
    print("\n" + "="*50)
    print("Starting Locust User Behavior Scenarios")
    print("="*50 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate final report with custom metrics"""
    print("\n" + "="*50)
    print("User Behavior Test Results")
    print("="*50 + "\n")
    
    # Cache performance
    total_cache_requests = metrics_storage['cache_hits'] + metrics_storage['cache_misses']
    if total_cache_requests > 0:
        cache_hit_rate = (metrics_storage['cache_hits'] / total_cache_requests) * 100
        print(f"Cache Performance:")
        print(f"  Hit Rate: {cache_hit_rate:.2f}%")
        print(f"  Total Hits: {metrics_storage['cache_hits']}")
        print(f"  Total Misses: {metrics_storage['cache_misses']}")
        print()
    
    # Model switching
    print(f"Model Switching:")
    print(f"  Total Switches: {metrics_storage['model_switches']}")
    print()
    
    # Response times by model
    print("Response Times by Model:")
    for model, times in metrics_storage['response_times_by_model'].items():
        if times:
            p50 = statistics.median(times)
            p95 = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            print(f"  {model}:")
            print(f"    P50: {p50:.2f}ms")
            print(f"    P95: {p95:.2f}ms")
    print()
    
    # Token usage and cost
    if metrics_storage['token_usage']:
        avg_tokens = statistics.mean(metrics_storage['token_usage'])
        total_tokens = sum(metrics_storage['token_usage'])
        print(f"Token Usage:")
        print(f"  Average per request: {avg_tokens:.0f}")
        print(f"  Total: {total_tokens:,}")
        print()
    
    if metrics_storage['cost_estimates']:
        total_cost = sum(metrics_storage['cost_estimates'])
        avg_cost = statistics.mean(metrics_storage['cost_estimates'])
        
        # Calculate cost reduction from caching
        if total_cache_requests > 0:
            cache_savings = (metrics_storage['cache_hits'] * avg_cost)
            cost_reduction = (cache_savings / (total_cost + cache_savings)) * 100
            print(f"Cost Analysis:")
            print(f"  Total Cost: ${total_cost:.4f}")
            print(f"  Cache Savings: ${cache_savings:.4f}")
            print(f"  Cost Reduction: {cost_reduction:.1f}%")
            print()
    
    # Conversation patterns
    if metrics_storage['conversation_lengths']:
        conversations = metrics_storage['conversation_lengths']
        avg_messages = statistics.mean([c['messages'] for c in conversations])
        avg_duration = statistics.mean([c['duration'] for c in conversations])
        
        print(f"Conversation Patterns:")
        print(f"  Total Conversations: {len(conversations)}")
        print(f"  Avg Messages per Conversation: {avg_messages:.1f}")
        print(f"  Avg Conversation Duration: {avg_duration:.1f}s")
        
        # Breakdown by user type
        user_types = {}
        for conv in conversations:
            user_type = conv['user_type']
            if user_type not in user_types:
                user_types[user_type] = []
            user_types[user_type].append(conv['messages'])
        
        for user_type, messages in user_types.items():
            avg = statistics.mean(messages)
            print(f"  {user_type}: {avg:.1f} messages/conversation")
    
    # Save results to file
    results = {
        'timestamp': datetime.now().isoformat(),
        'cache_hit_rate': cache_hit_rate if total_cache_requests > 0 else 0,
        'model_switches': metrics_storage['model_switches'],
        'total_tokens': sum(metrics_storage['token_usage']) if metrics_storage['token_usage'] else 0,
        'total_cost': total_cost if metrics_storage['cost_estimates'] else 0,
        'cost_reduction_percentage': cost_reduction if total_cache_requests > 0 else 0,
        'total_conversations': len(metrics_storage['conversation_lengths']),
    }
    
    with open('benchmarks/results/locust_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to benchmarks/results/locust_results.json")
    print("="*50 + "\n")


if __name__ == "__main__":
    # Can be run directly with: locust -f locust_scenarios.py
    print("Run with: locust -f benchmarks/load_tests/locust_scenarios.py --host http://localhost:8000")