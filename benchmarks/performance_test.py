"""Performance testing suite for chatbot system."""

import asyncio
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List

import aiohttp
import websockets


@dataclass
class PerformanceMetrics:
    """Performance test metrics."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Latency metrics (ms)
    min_latency: float = float('inf')
    max_latency: float = 0
    avg_latency: float = 0
    p50_latency: float = 0
    p95_latency: float = 0
    p99_latency: float = 0
    
    # Throughput
    requests_per_second: float = 0
    
    # Cache metrics
    cache_hits: int = 0
    cache_hit_rate: float = 0
    
    def calculate_percentiles(self, latencies: List[float]):
        """Calculate percentile metrics."""
        if not latencies:
            return
        
        sorted_latencies = sorted(latencies)
        self.min_latency = sorted_latencies[0]
        self.max_latency = sorted_latencies[-1]
        self.avg_latency = statistics.mean(latencies)
        self.p50_latency = sorted_latencies[int(len(latencies) * 0.50)]
        self.p95_latency = sorted_latencies[int(len(latencies) * 0.95)]
        self.p99_latency = sorted_latencies[int(len(latencies) * 0.99)]
    
    def print_summary(self):
        """Print performance summary."""
        print("\n" + "="*60)
        print("PERFORMANCE TEST RESULTS")
        print("="*60)
        print(f"Total Requests: {self.total_requests}")
        print(f"Successful: {self.successful_requests}")
        print(f"Failed: {self.failed_requests}")
        print(f"Success Rate: {(self.successful_requests/max(self.total_requests, 1))*100:.2f}%")
        print(f"\nLatency Metrics (ms):")
        print(f"  Min: {self.min_latency:.2f}")
        print(f"  Avg: {self.avg_latency:.2f}")
        print(f"  P50: {self.p50_latency:.2f}")
        print(f"  P95: {self.p95_latency:.2f}")
        print(f"  P99: {self.p99_latency:.2f}")
        print(f"  Max: {self.max_latency:.2f}")
        print(f"\nThroughput: {self.requests_per_second:.2f} req/s")
        print(f"\nCache Hit Rate: {self.cache_hit_rate*100:.2f}%")
        print("="*60)


class PerformanceTester:
    """Performance testing harness."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = "/api/v1"
        self.metrics = PerformanceMetrics()
        self.latencies = []
    
    async def test_http_endpoint(self, session: aiohttp.ClientSession) -> float:
        """Test HTTP chat endpoint."""
        start_time = time.time()
        
        payload = {
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
            "model": "model-3.5-turbo",
            "temperature": 0.7,
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
        }
        
        try:
            async with session.post(
                f"{self.base_url}{self.api_prefix}/chat",
                json=payload,
                headers={"Authorization": "Bearer test-token"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.metrics.successful_requests += 1
                    if data.get("cached"):
                        self.metrics.cache_hits += 1
                else:
                    self.metrics.failed_requests += 1
        except Exception as e:
            print(f"Request failed: {e}")
            self.metrics.failed_requests += 1
        
        latency = (time.time() - start_time) * 1000
        return latency
    
    async def test_websocket_connection(self) -> float:
        """Test WebSocket connection and messaging."""
        start_time = time.time()
        
        try:
            uri = f"ws://localhost:8000{self.api_prefix}/ws?tenant_id=550e8400-e29b-41d4-a716-446655440000"
            
            async with websockets.connect(uri) as websocket:
                # Send auth
                auth_msg = json.dumps({
                    "type": "auth_request",
                    "data": {"token": "valid-token"}
                })
                await websocket.send(auth_msg)
                await websocket.recv()  # Auth response
                
                # Send message
                chat_msg = json.dumps({
                    "type": "chat_message",
                    "data": {
                        "content": "Hello WebSocket!",
                        "model": "model-3.5-turbo",
                        "stream": False
                    }
                })
                await websocket.send(chat_msg)
                
                # Receive response
                response = await websocket.recv()
                if response:
                    self.metrics.successful_requests += 1
                else:
                    self.metrics.failed_requests += 1
                    
        except Exception as e:
            print(f"WebSocket test failed: {e}")
            self.metrics.failed_requests += 1
        
        latency = (time.time() - start_time) * 1000
        return latency
    
    async def run_concurrent_test(
        self,
        num_requests: int = 100,
        concurrent_users: int = 10
    ):
        """Run concurrent performance test."""
        print(f"\nRunning {num_requests} requests with {concurrent_users} concurrent users...")
        
        self.metrics = PerformanceMetrics()
        self.latencies = []
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Create tasks for concurrent requests
            tasks = []
            for i in range(num_requests):
                if i % 2 == 0:
                    # Mix HTTP and WebSocket tests
                    task = self.test_http_endpoint(session)
                else:
                    task = self.test_websocket_connection()
                tasks.append(task)
                
                # Control concurrency
                if len(tasks) >= concurrent_users:
                    results = await asyncio.gather(*tasks)
                    self.latencies.extend(results)
                    self.metrics.total_requests += len(tasks)
                    tasks = []
            
            # Process remaining tasks
            if tasks:
                results = await asyncio.gather(*tasks)
                self.latencies.extend(results)
                self.metrics.total_requests += len(tasks)
        
        # Calculate metrics
        duration = time.time() - start_time
        self.metrics.requests_per_second = self.metrics.total_requests / duration
        self.metrics.cache_hit_rate = self.metrics.cache_hits / max(self.metrics.successful_requests, 1)
        self.metrics.calculate_percentiles(self.latencies)
        
        return self.metrics
    
    async def run_stress_test(self, duration_seconds: int = 60):
        """Run stress test for specified duration."""
        print(f"\nRunning stress test for {duration_seconds} seconds...")
        
        self.metrics = PerformanceMetrics()
        self.latencies = []
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                # Fire requests continuously
                tasks = []
                for _ in range(50):  # Batch of 50 requests
                    task = self.test_http_endpoint(session)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, float):
                        self.latencies.append(result)
                    
                self.metrics.total_requests += len(tasks)
                
                # Brief pause to avoid overwhelming
                await asyncio.sleep(0.1)
        
        # Calculate final metrics
        duration = time.time() - start_time
        self.metrics.requests_per_second = self.metrics.total_requests / duration
        self.metrics.cache_hit_rate = self.metrics.cache_hits / max(self.metrics.successful_requests, 1)
        self.metrics.calculate_percentiles(self.latencies)
        
        return self.metrics
    
    async def test_cache_performance(self):
        """Test cache hit rate and performance."""
        print("\nTesting cache performance...")
        
        queries = [
            "What's the weather like?",
            "Tell me a joke",
            "What's the weather like?",  # Duplicate
            "How are you?",
            "Tell me a joke",  # Duplicate
            "What can you help with?",
            "How are you?",  # Duplicate
        ]
        
        cache_test_metrics = PerformanceMetrics()
        
        async with aiohttp.ClientSession() as session:
            for query in queries:
                start_time = time.time()
                
                payload = {
                    "messages": [{"role": "user", "content": query}],
                    "model": "model-3.5-turbo",
                    "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
                }
                
                try:
                    async with session.post(
                        f"{self.base_url}{self.api_prefix}/chat",
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("cached"):
                                cache_test_metrics.cache_hits += 1
                                print(f"  Cache HIT: {query[:30]}...")
                            else:
                                print(f"  Cache MISS: {query[:30]}...")
                            cache_test_metrics.successful_requests += 1
                except Exception as e:
                    print(f"  Request failed: {e}")
                    cache_test_metrics.failed_requests += 1
                
                cache_test_metrics.total_requests += 1
                
                # Small delay between requests
                await asyncio.sleep(0.1)
        
        cache_test_metrics.cache_hit_rate = (
            cache_test_metrics.cache_hits / max(cache_test_metrics.successful_requests, 1)
        )
        
        print(f"\nCache Performance Results:")
        print(f"  Total Requests: {cache_test_metrics.total_requests}")
        print(f"  Cache Hits: {cache_test_metrics.cache_hits}")
        print(f"  Cache Hit Rate: {cache_test_metrics.cache_hit_rate*100:.2f}%")
        
        return cache_test_metrics


async def main():
    """Run performance test suite."""
    tester = PerformanceTester()
    
    print("\n" + "="*60)
    print("CHATBOT SYSTEM PERFORMANCE TEST SUITE")
    print("="*60)
    
    # Test 1: Concurrent users
    print("\nTest 1: Concurrent User Load")
    metrics = await tester.run_concurrent_test(num_requests=100, concurrent_users=10)
    metrics.print_summary()
    
    # Verify P95 < 200ms for cached responses
    if metrics.p95_latency < 200:
        print("✅ PASS: P95 latency < 200ms requirement met")
    else:
        print("❌ FAIL: P95 latency > 200ms")
    
    # Test 2: Cache performance
    print("\nTest 2: Cache Performance")
    cache_metrics = await tester.test_cache_performance()
    
    # Verify 42% cache hit rate
    if cache_metrics.cache_hit_rate >= 0.42:
        print("✅ PASS: Cache hit rate >= 42% requirement met")
    else:
        print("❌ FAIL: Cache hit rate < 42%")
    
    # Test 3: Stress test
    print("\nTest 3: Stress Test")
    stress_metrics = await tester.run_stress_test(duration_seconds=30)
    stress_metrics.print_summary()
    
    # Verify throughput > 1000 req/s
    if stress_metrics.requests_per_second > 1000:
        print("✅ PASS: Throughput > 1000 req/s requirement met")
    else:
        print("⚠️  INFO: Current throughput:", stress_metrics.requests_per_second)
    
    print("\n" + "="*60)
    print("PERFORMANCE TEST SUITE COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())