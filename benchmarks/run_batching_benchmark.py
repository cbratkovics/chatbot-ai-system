#!/usr/bin/env python3
"""
Request Batching Benchmark Runner
Author: Christopher J. Bratkovics
Purpose: Measure API call reduction through intelligent request batching
"""

import argparse
import asyncio
import csv
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime
import os
from collections import deque
import threading

@dataclass
class BatchingMetrics:
    total_requests: int = 0
    total_api_calls: int = 0
    batch_sizes: List[int] = field(default_factory=list)
    latencies: List[float] = field(default_factory=list)
    batch_wait_times: List[float] = field(default_factory=list)
    queue_depths: List[int] = field(default_factory=list)
    processing_times: List[float] = field(default_factory=list)
    failed_requests: int = 0
    retry_count: int = 0
    rate_limit_hits: int = 0
    total_tokens: int = 0
    start_time: float = 0
    end_time: float = 0
    
    @property
    def total_time(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0
    
    @property
    def throughput(self) -> float:
        return self.total_requests / self.total_time if self.total_time > 0 else 0
    
    @property
    def avg_batch_size(self) -> float:
        return np.mean(self.batch_sizes) if self.batch_sizes else 1

class EmbeddingRequest:
    """Represents a single embedding request"""
    
    def __init__(self, text: str, request_id: int):
        self.text = text
        self.request_id = request_id
        self.timestamp = time.time()
        self.completed = False
        self.result = None
        self.latency = None
    
    def complete(self, result: Any):
        """Mark request as completed"""
        self.completed = True
        self.result = result
        self.latency = time.time() - self.timestamp

class BatchProcessor:
    """Handles batch formation and processing"""
    
    def __init__(self, batch_size: int = 8, wait_window_ms: int = 50, max_wait_ms: int = 100):
        self.batch_size = batch_size
        self.wait_window_ms = wait_window_ms
        self.max_wait_ms = max_wait_ms
        self.queue = deque()
        self.metrics = BatchingMetrics()
        self.lock = threading.Lock()
        self.processing = False
    
    async def add_request(self, request: EmbeddingRequest) -> None:
        """Add request to batch queue"""
        with self.lock:
            self.queue.append(request)
            self.metrics.queue_depths.append(len(self.queue))
        
        # Check if we should process batch
        if len(self.queue) >= self.batch_size:
            await self.process_batch()
        elif len(self.queue) == 1:
            # Start wait timer for first request
            asyncio.create_task(self.wait_and_process())
    
    async def wait_and_process(self) -> None:
        """Wait for batch formation window"""
        start_wait = time.time()
        await asyncio.sleep(self.wait_window_ms / 1000)
        
        with self.lock:
            if self.queue and not self.processing:
                wait_time = (time.time() - start_wait) * 1000
                self.metrics.batch_wait_times.append(wait_time)
                asyncio.create_task(self.process_batch())
    
    async def process_batch(self) -> None:
        """Process a batch of requests"""
        with self.lock:
            if self.processing or not self.queue:
                return
            
            self.processing = True
            batch_size = min(len(self.queue), self.batch_size)
            batch = [self.queue.popleft() for _ in range(batch_size)]
        
        start_time = time.time()
        
        try:
            # Simulate API call with batched requests
            await self.call_embedding_api(batch)
            
            # Record metrics
            self.metrics.total_api_calls += 1
            self.metrics.batch_sizes.append(len(batch))
            self.metrics.processing_times.append(time.time() - start_time)
            
            # Complete requests
            for request in batch:
                request.complete(f"embedding_vector_{request.request_id}")
                self.metrics.latencies.append(request.latency)
                self.metrics.total_requests += 1
        
        except Exception as e:
            self.metrics.failed_requests += len(batch)
            self.metrics.retry_count += 1
        
        finally:
            with self.lock:
                self.processing = False
    
    async def call_embedding_api(self, batch: List[EmbeddingRequest]) -> Dict:
        """Simulate embedding API call"""
        # Calculate tokens based on text length
        total_tokens = sum(len(req.text.split()) * 1.3 for req in batch)
        self.metrics.total_tokens += int(total_tokens)
        
        # Simulate API latency (faster for batched requests)
        base_latency = 0.08  # 80ms base
        per_request_latency = 0.01  # 10ms per request
        total_latency = base_latency + (per_request_latency * len(batch))
        
        await asyncio.sleep(total_latency)
        
        # Simulate occasional rate limiting
        if np.random.random() < 0.02:  # 2% chance
            self.metrics.rate_limit_hits += 1
            await asyncio.sleep(1.0)  # Rate limit delay
        
        return {
            "embeddings": [f"vector_{req.request_id}" for req in batch],
            "tokens_used": int(total_tokens)
        }

class SequentialProcessor:
    """Process requests sequentially without batching"""
    
    def __init__(self):
        self.metrics = BatchingMetrics()
    
    async def process_request(self, request: EmbeddingRequest) -> None:
        """Process a single request"""
        start_time = time.time()
        
        try:
            # Simulate individual API call
            await self.call_embedding_api(request)
            
            # Record metrics
            self.metrics.total_api_calls += 1
            self.metrics.batch_sizes.append(1)
            self.metrics.processing_times.append(time.time() - start_time)
            
            request.complete(f"embedding_vector_{request.request_id}")
            self.metrics.latencies.append(request.latency)
            self.metrics.total_requests += 1
        
        except Exception as e:
            self.metrics.failed_requests += 1
            self.metrics.retry_count += 1
    
    async def call_embedding_api(self, request: EmbeddingRequest) -> Dict:
        """Simulate embedding API call for single request"""
        tokens = len(request.text.split()) * 1.3
        self.metrics.total_tokens += int(tokens)
        
        # Simulate API latency (slower for individual requests)
        latency = np.random.uniform(0.4, 0.6)  # 400-600ms
        await asyncio.sleep(latency)
        
        # Higher chance of rate limiting with sequential calls
        if np.random.random() < 0.05:  # 5% chance
            self.metrics.rate_limit_hits += 1
            await asyncio.sleep(2.0)  # Rate limit delay
        
        return {
            "embedding": f"vector_{request.request_id}",
            "tokens_used": int(tokens)
        }

class BenchmarkRunner:
    """Execute batching benchmark scenarios"""
    
    def __init__(self, mode: str = "sequential"):
        self.mode = mode
        self.requests = self._generate_requests()
    
    def _generate_requests(self) -> List[EmbeddingRequest]:
        """Generate test embedding requests"""
        requests = []
        
        # Different text types and lengths
        text_templates = [
            # Short texts (< 100 tokens)
            "Search query: {query}",
            "User input: {text}",
            "Category: {category}",
            
            # Medium texts (100-500 tokens)
            "Document chunk: {content} " * 20,
            "Product description: {description} " * 15,
            "Article excerpt: {excerpt} " * 25,
            
            # Long texts (500-1000 tokens)
            "Full document: {document} " * 50,
            "Research paper abstract: {abstract} " * 40,
        ]
        
        for i in range(1000):
            template = text_templates[i % len(text_templates)]
            text = template.format(
                query=f"query_{i}",
                text=f"text_{i}",
                category=f"category_{i % 10}",
                content=f"content_{i}",
                description=f"desc_{i}",
                excerpt=f"excerpt_{i}",
                document=f"doc_{i}",
                abstract=f"abstract_{i}"
            )
            requests.append(EmbeddingRequest(text, i))
        
        return requests
    
    async def run_sequential(self) -> BatchingMetrics:
        """Run sequential processing benchmark"""
        processor = SequentialProcessor()
        processor.metrics.start_time = time.time()
        
        print(f"Processing {len(self.requests)} requests sequentially...")
        
        # Process with limited concurrency to simulate realistic load
        semaphore = asyncio.Semaphore(10)  # 10 concurrent requests max
        
        async def process_with_limit(req):
            async with semaphore:
                await processor.process_request(req)
        
        # Process all requests
        tasks = [process_with_limit(req) for req in self.requests]
        
        # Process in batches for progress reporting
        batch_size = 100
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            await asyncio.gather(*batch)
            print(f"  Processed {min(i+batch_size, len(tasks))}/{len(tasks)} requests...")
        
        processor.metrics.end_time = time.time()
        return processor.metrics
    
    async def run_batched(self) -> BatchingMetrics:
        """Run batched processing benchmark"""
        processor = BatchProcessor(batch_size=8, wait_window_ms=50)
        processor.metrics.start_time = time.time()
        
        print(f"Processing {len(self.requests)} requests with batching...")
        
        # Add requests to batch processor
        for i, request in enumerate(self.requests):
            await processor.add_request(request)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"  Added {i+1}/{len(self.requests)} requests to queue...")
            
            # Small delay to simulate incoming request rate
            if i < len(self.requests) - 1:
                await asyncio.sleep(0.001)  # 1ms between requests
        
        # Wait for all batches to complete
        while processor.queue or processor.processing:
            await asyncio.sleep(0.1)
        
        processor.metrics.end_time = time.time()
        return processor.metrics

def save_comparison_results(sequential: BatchingMetrics, batched: BatchingMetrics):
    """Save comparison results to CSV"""
    
    # Calculate improvements
    api_reduction = (1 - batched.total_api_calls / sequential.total_api_calls) * 100
    throughput_improvement = (batched.throughput / sequential.throughput - 1) * 100
    latency_improvement = (1 - np.mean(batched.latencies) / np.mean(sequential.latencies)) * 100
    
    # Prepare CSV data
    rows = [
        ["metric", "sequential", "batched", "improvement", "unit"],
        ["total_requests", sequential.total_requests, batched.total_requests, 0, "count"],
        ["total_api_calls", sequential.total_api_calls, batched.total_api_calls,
         sequential.total_api_calls - batched.total_api_calls, "count"],
        ["api_call_reduction", 0, round(api_reduction, 2), round(api_reduction, 2), "%"],
        ["avg_batch_size", 1, round(batched.avg_batch_size, 2), 
         round(batched.avg_batch_size - 1, 2), "requests"],
        ["total_processing_time_sec", round(sequential.total_time, 2), 
         round(batched.total_time, 2),
         round(sequential.total_time - batched.total_time, 2), "seconds"],
        ["throughput_requests_per_sec", round(sequential.throughput, 2),
         round(batched.throughput, 2),
         round(batched.throughput - sequential.throughput, 2), "req/s"],
        ["throughput_improvement", 0, round(throughput_improvement, 2),
         round(throughput_improvement, 2), "%"],
        ["avg_latency_ms", round(np.mean(sequential.latencies) * 1000, 2),
         round(np.mean(batched.latencies) * 1000, 2),
         round((np.mean(sequential.latencies) - np.mean(batched.latencies)) * 1000, 2), "ms"],
        ["p50_latency_ms", round(np.percentile(sequential.latencies, 50) * 1000),
         round(np.percentile(batched.latencies, 50) * 1000),
         round((np.percentile(sequential.latencies, 50) - np.percentile(batched.latencies, 50)) * 1000), "ms"],
        ["p95_latency_ms", round(np.percentile(sequential.latencies, 95) * 1000),
         round(np.percentile(batched.latencies, 95) * 1000),
         round((np.percentile(sequential.latencies, 95) - np.percentile(batched.latencies, 95)) * 1000), "ms"],
        ["p99_latency_ms", round(np.percentile(sequential.latencies, 99) * 1000),
         round(np.percentile(batched.latencies, 99) * 1000),
         round((np.percentile(sequential.latencies, 99) - np.percentile(batched.latencies, 99)) * 1000), "ms"],
        ["rate_limit_hits", sequential.rate_limit_hits, batched.rate_limit_hits,
         sequential.rate_limit_hits - batched.rate_limit_hits, "count"],
        ["failed_requests", sequential.failed_requests, batched.failed_requests,
         sequential.failed_requests - batched.failed_requests, "count"],
        ["retry_count", sequential.retry_count, batched.retry_count,
         sequential.retry_count - batched.retry_count, "count"],
        ["total_tokens_processed", sequential.total_tokens, batched.total_tokens, 0, "tokens"],
    ]
    
    if batched.batch_wait_times:
        rows.append(["avg_batch_wait_ms", 0, round(np.mean(batched.batch_wait_times), 2),
                    round(np.mean(batched.batch_wait_times), 2), "ms"])
    
    if batched.queue_depths:
        rows.append(["avg_queue_depth", 0, round(np.mean(batched.queue_depths), 2),
                    round(np.mean(batched.queue_depths), 2), "requests"])
        rows.append(["max_queue_depth", 0, max(batched.queue_depths),
                    max(batched.queue_depths), "requests"])
    
    # Write to CSV
    output_path = "docs/benchmarks/batching_reduction/results.csv"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\nResults saved to {output_path}")
    print(f"API call reduction: {api_reduction:.2f}%")
    print(f"Throughput improvement: {throughput_improvement:.2f}%")
    print(f"Average latency improvement: {latency_improvement:.2f}%")

async def main():
    parser = argparse.ArgumentParser(description="Run request batching benchmark")
    parser.add_argument("--mode", choices=["sequential", "batched", "both"],
                       default="both", help="Benchmark mode")
    parser.add_argument("--compare", action="store_true",
                       help="Generate comparison report")
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner()
    
    sequential_metrics = None
    batched_metrics = None
    
    if args.mode in ["sequential", "both"]:
        print("\n" + "="*60)
        print("SEQUENTIAL PROCESSING BENCHMARK")
        print("="*60)
        sequential_metrics = await runner.run_sequential()
        print(f"Completed: {sequential_metrics.total_api_calls} API calls")
        print(f"Throughput: {sequential_metrics.throughput:.2f} req/s")
    
    if args.mode in ["batched", "both"]:
        print("\n" + "="*60)
        print("BATCHED PROCESSING BENCHMARK")
        print("="*60)
        runner = BenchmarkRunner()  # Fresh instance for fair comparison
        batched_metrics = await runner.run_batched()
        print(f"Completed: {batched_metrics.total_api_calls} API calls")
        print(f"Throughput: {batched_metrics.throughput:.2f} req/s")
        print(f"Average batch size: {batched_metrics.avg_batch_size:.2f}")
    
    if (args.mode == "both" or args.compare) and sequential_metrics and batched_metrics:
        print("\n" + "="*60)
        print("GENERATING COMPARISON REPORT")
        print("="*60)
        save_comparison_results(sequential_metrics, batched_metrics)

if __name__ == "__main__":
    asyncio.run(main())