#!/usr/bin/env python3
"""
Semantic Cache Benchmark Runner
Author: Christopher J. Bratkovics
Purpose: Measure performance improvements from semantic caching
"""

import argparse
import asyncio
import csv
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import hashlib
import numpy as np
from datetime import datetime
import os

@dataclass
class BenchmarkMetrics:
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    response_times: List[float] = None
    cache_lookup_times: List[float] = None
    embedding_times: List[float] = None
    
    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.cache_lookup_times is None:
            self.cache_lookup_times = []
        if self.embedding_times is None:
            self.embedding_times = []

class SemanticCache:
    """Simulated semantic cache for benchmarking"""
    
    def __init__(self, similarity_threshold: float = 0.95):
        self.cache = {}
        self.embeddings = {}
        self.similarity_threshold = similarity_threshold
        self.stats = {"hits": 0, "misses": 0}
    
    async def get(self, query: str) -> Dict[str, Any]:
        """Simulate cache lookup with realistic timing"""
        start_time = time.time()
        
        # Simulate embedding generation
        await asyncio.sleep(0.045)  # 45ms for embedding
        
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        # Simulate vector similarity search
        await asyncio.sleep(0.012)  # 12ms for search
        
        lookup_time = time.time() - start_time
        
        if query_hash in self.cache:
            self.stats["hits"] += 1
            return {
                "hit": True,
                "response": self.cache[query_hash],
                "lookup_time": lookup_time
            }
        
        self.stats["misses"] += 1
        return {
            "hit": False,
            "response": None,
            "lookup_time": lookup_time
        }
    
    async def set(self, query: str, response: str, tokens: Dict[str, int]):
        """Store response in cache"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        self.cache[query_hash] = {
            "response": response,
            "tokens": tokens,
            "timestamp": time.time()
        }

class LLMSimulator:
    """Simulate LLM API calls with realistic metrics"""
    
    def __init__(self):
        self.cost_per_1k_tokens = 0.002  # GPT-3.5-turbo pricing
        
    async def generate(self, query: str) -> Dict[str, Any]:
        """Simulate LLM response generation"""
        start_time = time.time()
        
        # Simulate API latency (1.5-2.5 seconds)
        latency = np.random.uniform(1.5, 2.5)
        await asyncio.sleep(latency)
        
        # Calculate token counts based on query length
        input_tokens = len(query.split()) * 1.3  # Rough approximation
        output_tokens = np.random.randint(150, 350)  # Variable response length
        
        response = f"Generated response for: {query[:50]}..."
        
        return {
            "response": response,
            "input_tokens": int(input_tokens),
            "output_tokens": output_tokens,
            "total_tokens": int(input_tokens) + output_tokens,
            "response_time": time.time() - start_time,
            "cost": (int(input_tokens) + output_tokens) / 1000 * self.cost_per_1k_tokens
        }

class BenchmarkRunner:
    """Execute and measure cache benchmark scenarios"""
    
    def __init__(self, use_cache: bool = False):
        self.use_cache = use_cache
        self.cache = SemanticCache() if use_cache else None
        self.llm = LLMSimulator()
        self.metrics = BenchmarkMetrics()
        self.queries = self._generate_queries()
    
    def _generate_queries(self) -> List[str]:
        """Generate test queries with controlled duplication"""
        base_queries = [
            "How do I implement a binary search tree in Python?",
            "Explain the concept of microservices architecture",
            "What are the best practices for API design?",
            "How does garbage collection work in Java?",
            "Explain the difference between TCP and UDP",
            "What is the CAP theorem in distributed systems?",
            "How do I optimize database queries?",
            "Explain OAuth 2.0 authentication flow",
            "What are design patterns in software engineering?",
            "How does containerization work with Docker?",
            # Add more unique queries...
        ]
        
        # Extend to 350 unique queries
        unique_queries = []
        for i in range(350):
            query = base_queries[i % len(base_queries)]
            if i >= len(base_queries):
                query = f"{query} (variation {i // len(base_queries)})"
            unique_queries.append(query)
        
        # Create 500 total queries with 30% duplicates
        all_queries = unique_queries.copy()
        
        # Add 150 duplicates randomly
        import random
        for _ in range(150):
            all_queries.append(random.choice(unique_queries[:100]))  # Duplicate from first 100
        
        random.shuffle(all_queries)
        return all_queries
    
    async def process_request(self, query: str) -> None:
        """Process a single request with or without cache"""
        self.metrics.total_requests += 1
        
        if self.use_cache:
            cache_result = await self.cache.get(query)
            self.metrics.cache_lookup_times.append(cache_result["lookup_time"])
            
            if cache_result["hit"]:
                self.metrics.cache_hits += 1
                # Use cached token counts
                cached_data = cache_result["response"]
                self.metrics.total_input_tokens += cached_data["tokens"]["input"]
                self.metrics.total_output_tokens += cached_data["tokens"]["output"]
                self.metrics.response_times.append(0.05)  # Cache hit response time
                return
            else:
                self.metrics.cache_misses += 1
        
        # Generate new response
        result = await self.llm.generate(query)
        
        self.metrics.total_input_tokens += result["input_tokens"]
        self.metrics.total_output_tokens += result["output_tokens"]
        self.metrics.total_tokens += result["total_tokens"]
        self.metrics.total_cost_usd += result["cost"]
        self.metrics.response_times.append(result["response_time"])
        
        if self.use_cache:
            await self.cache.set(query, result["response"], {
                "input": result["input_tokens"],
                "output": result["output_tokens"]
            })
    
    async def run(self) -> BenchmarkMetrics:
        """Execute the benchmark"""
        print(f"Starting benchmark - Mode: {'Optimized (with cache)' if self.use_cache else 'Baseline (no cache)'}")
        print(f"Processing {len(self.queries)} requests...")
        
        start_time = time.time()
        
        # Process requests with controlled concurrency
        batch_size = 10
        for i in range(0, len(self.queries), batch_size):
            batch = self.queries[i:i+batch_size]
            await asyncio.gather(*[self.process_request(q) for q in batch])
            
            # Progress indicator
            if (i + batch_size) % 50 == 0:
                print(f"  Processed {min(i + batch_size, len(self.queries))}/{len(self.queries)} requests...")
        
        total_time = time.time() - start_time
        
        # Calculate final metrics
        self.metrics.total_tokens = self.metrics.total_input_tokens + self.metrics.total_output_tokens
        self.metrics.total_cost_usd = self.metrics.total_tokens / 1000 * self.llm.cost_per_1k_tokens
        
        print(f"Completed in {total_time:.2f} seconds")
        if self.use_cache:
            hit_rate = (self.metrics.cache_hits / self.metrics.total_requests) * 100
            print(f"Cache hit rate: {hit_rate:.1f}%")
        
        return self.metrics

def save_results(baseline_metrics: BenchmarkMetrics, optimized_metrics: BenchmarkMetrics):
    """Save benchmark results to CSV"""
    
    # Calculate improvements
    token_reduction = (1 - optimized_metrics.total_tokens / baseline_metrics.total_tokens) * 100
    cost_reduction = (1 - optimized_metrics.total_cost_usd / baseline_metrics.total_cost_usd) * 100
    
    # Prepare CSV data
    rows = [
        ["metric", "baseline", "optimized", "improvement", "unit"],
        ["total_requests", baseline_metrics.total_requests, optimized_metrics.total_requests, 0, "%"],
        ["cache_hits", 0, optimized_metrics.cache_hits, optimized_metrics.cache_hits, "count"],
        ["cache_misses", baseline_metrics.total_requests, optimized_metrics.cache_misses, 
         -(baseline_metrics.total_requests - optimized_metrics.cache_misses), "count"],
        ["cache_hit_rate", 0, round((optimized_metrics.cache_hits / optimized_metrics.total_requests) * 100, 2),
         round((optimized_metrics.cache_hits / optimized_metrics.total_requests) * 100, 2), "%"],
        ["total_input_tokens", baseline_metrics.total_input_tokens, optimized_metrics.total_input_tokens,
         baseline_metrics.total_input_tokens - optimized_metrics.total_input_tokens, "tokens"],
        ["total_output_tokens", baseline_metrics.total_output_tokens, optimized_metrics.total_output_tokens,
         baseline_metrics.total_output_tokens - optimized_metrics.total_output_tokens, "tokens"],
        ["total_tokens", baseline_metrics.total_tokens, optimized_metrics.total_tokens,
         baseline_metrics.total_tokens - optimized_metrics.total_tokens, "tokens"],
        ["token_reduction", 0, round(token_reduction, 2), round(token_reduction, 2), "%"],
        ["baseline_cost_usd", round(baseline_metrics.total_cost_usd, 3), 
         round(optimized_metrics.total_cost_usd, 3),
         round(baseline_metrics.total_cost_usd - optimized_metrics.total_cost_usd, 3), "USD"],
        ["cost_reduction", 0, round(cost_reduction, 2), round(cost_reduction, 2), "%"],
    ]
    
    # Add response time percentiles
    for metrics, name in [(baseline_metrics, "baseline"), (optimized_metrics, "optimized")]:
        if metrics.response_times:
            p50 = np.percentile(metrics.response_times, 50) * 1000
            p95 = np.percentile(metrics.response_times, 95) * 1000
            p99 = np.percentile(metrics.response_times, 99) * 1000
            
            if name == "baseline":
                baseline_p50, baseline_p95, baseline_p99 = p50, p95, p99
            else:
                rows.extend([
                    ["p50_response_time_ms", round(baseline_p50), round(p50), 
                     round(baseline_p50 - p50), "ms"],
                    ["p95_response_time_ms", round(baseline_p95), round(p95),
                     round(baseline_p95 - p95), "ms"],
                    ["p99_response_time_ms", round(baseline_p99), round(p99),
                     round(baseline_p99 - p99), "ms"],
                ])
    
    # Write to CSV
    output_path = "docs/benchmarks/cache_savings/results.csv"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\nResults saved to {output_path}")
    print(f"Token reduction: {token_reduction:.2f}%")
    print(f"Cost reduction: {cost_reduction:.2f}%")

async def main():
    parser = argparse.ArgumentParser(description="Run semantic cache benchmark")
    parser.add_argument("--mode", choices=["baseline", "optimized", "both"], 
                       default="both", help="Benchmark mode")
    parser.add_argument("--report", action="store_true", 
                       help="Generate comparison report")
    
    args = parser.parse_args()
    
    if args.mode in ["baseline", "both"]:
        print("\n" + "="*60)
        print("BASELINE BENCHMARK (No Cache)")
        print("="*60)
        runner = BenchmarkRunner(use_cache=False)
        baseline_metrics = await runner.run()
    
    if args.mode in ["optimized", "both"]:
        print("\n" + "="*60)
        print("OPTIMIZED BENCHMARK (With Semantic Cache)")
        print("="*60)
        runner = BenchmarkRunner(use_cache=True)
        optimized_metrics = await runner.run()
    
    if args.mode == "both" or args.report:
        print("\n" + "="*60)
        print("GENERATING COMPARISON REPORT")
        print("="*60)
        save_results(baseline_metrics, optimized_metrics)

if __name__ == "__main__":
    asyncio.run(main())