#!/usr/bin/env python3
"""
Real-time latency monitoring and analysis for benchmark tests.
Tracks latency metrics and generates performance reports.
"""

import asyncio
import json
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
import numpy as np
from prometheus_client import Histogram, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import aiohttp
from aiohttp import web
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
latency_histogram = Histogram(
    'api_request_duration_seconds',
    'API request latency',
    ['endpoint', 'method', 'model', 'status']
)

websocket_latency = Histogram(
    'websocket_message_latency_seconds',
    'WebSocket message latency',
    ['message_type', 'model']
)

cache_latency = Histogram(
    'cache_operation_latency_seconds',
    'Cache operation latency',
    ['operation', 'hit']
)

request_counter = Counter(
    'api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

active_connections = Gauge(
    'websocket_active_connections',
    'Active WebSocket connections'
)

model_latency = Histogram(
    'model_inference_latency_seconds',
    'Model inference latency',
    ['model', 'provider']
)


class LatencyTracker:
    """Track and analyze latency metrics in real-time"""
    
    def __init__(self, window_size: int = 1000, percentiles: List[int] = None):
        """
        Initialize latency tracker.
        
        Args:
            window_size: Size of sliding window for real-time metrics
            percentiles: List of percentiles to track (default: [50, 95, 99])
        """
        self.window_size = window_size
        self.percentiles = percentiles or [50, 95, 99]
        
        # Sliding windows for different metric types
        self.windows = defaultdict(lambda: deque(maxlen=window_size))
        
        # Aggregated metrics
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'sum': 0,
            'min': float('inf'),
            'max': 0,
            'percentiles': {},
            'histogram': [],
        })
        
        # Time-series data for graphing
        self.time_series = defaultdict(list)
        
        # Start time for rate calculations
        self.start_time = time.time()
        
        # HTTP server for metrics endpoint
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup HTTP routes for metrics endpoint"""
        self.app.router.add_get('/metrics', self.handle_metrics)
        self.app.router.add_get('/metrics/json', self.handle_json_metrics)
        self.app.router.add_get('/metrics/graph', self.handle_graph)
    
    async def handle_metrics(self, request):
        """Prometheus metrics endpoint"""
        metrics = generate_latest()
        return web.Response(body=metrics, content_type=CONTENT_TYPE_LATEST)
    
    async def handle_json_metrics(self, request):
        """JSON metrics endpoint"""
        metrics = self.get_current_metrics()
        return web.json_response(metrics)
    
    async def handle_graph(self, request):
        """Generate and serve latency graph"""
        graph_path = self.generate_latency_graph()
        return web.FileResponse(graph_path)
    
    def record_latency(
        self,
        metric_type: str,
        latency_ms: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Record a latency measurement.
        
        Args:
            metric_type: Type of metric (e.g., 'api', 'websocket', 'cache')
            latency_ms: Latency in milliseconds
            labels: Additional labels for the metric
        """
        # Add to sliding window
        self.windows[metric_type].append(latency_ms)
        
        # Update aggregated metrics
        metrics = self.metrics[metric_type]
        metrics['count'] += 1
        metrics['sum'] += latency_ms
        metrics['min'] = min(metrics['min'], latency_ms)
        metrics['max'] = max(metrics['max'], latency_ms)
        metrics['histogram'].append(latency_ms)
        
        # Add to time series
        self.time_series[metric_type].append({
            'timestamp': datetime.now().isoformat(),
            'latency': latency_ms,
            'labels': labels or {}
        })
        
        # Update Prometheus metrics
        if metric_type == 'api':
            latency_histogram.labels(
                endpoint=labels.get('endpoint', '/unknown'),
                method=labels.get('method', 'GET'),
                model=labels.get('model', 'unknown'),
                status=labels.get('status', '200')
            ).observe(latency_ms / 1000)  # Convert to seconds
        elif metric_type == 'websocket':
            websocket_latency.labels(
                message_type=labels.get('message_type', 'unknown'),
                model=labels.get('model', 'unknown')
            ).observe(latency_ms / 1000)
        elif metric_type == 'cache':
            cache_latency.labels(
                operation=labels.get('operation', 'get'),
                hit=labels.get('hit', 'false')
            ).observe(latency_ms / 1000)
        elif metric_type == 'model':
            model_latency.labels(
                model=labels.get('model', 'unknown'),
                provider=labels.get('provider', 'unknown')
            ).observe(latency_ms / 1000)
    
    def calculate_percentiles(self, data: List[float]) -> Dict[int, float]:
        """Calculate percentiles for given data"""
        if not data:
            return {p: 0 for p in self.percentiles}
        
        sorted_data = sorted(data)
        result = {}
        
        for p in self.percentiles:
            index = int(len(sorted_data) * p / 100)
            if index >= len(sorted_data):
                index = len(sorted_data) - 1
            result[p] = sorted_data[index]
        
        return result
    
    def get_current_metrics(self) -> Dict:
        """Get current metrics snapshot"""
        elapsed_time = time.time() - self.start_time
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'metrics': {}
        }
        
        for metric_type, window in self.windows.items():
            if not window:
                continue
            
            window_list = list(window)
            metrics = self.metrics[metric_type]
            
            # Calculate percentiles
            percentiles = self.calculate_percentiles(window_list)
            
            # Calculate rate
            rate = metrics['count'] / elapsed_time if elapsed_time > 0 else 0
            
            results['metrics'][metric_type] = {
                'count': metrics['count'],
                'rate_per_second': rate,
                'mean': metrics['sum'] / metrics['count'] if metrics['count'] > 0 else 0,
                'min': metrics['min'] if metrics['min'] != float('inf') else 0,
                'max': metrics['max'],
                'percentiles': {
                    f'p{p}': value for p, value in percentiles.items()
                },
                'current_window_size': len(window),
            }
        
        return results
    
    def generate_latency_graph(self, output_path: str = None) -> str:
        """
        Generate latency distribution graphs.
        
        Args:
            output_path: Path to save the graph
            
        Returns:
            Path to the generated graph
        """
        if not output_path:
            output_path = 'benchmarks/results/latency_distribution.png'
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Create subplots for different metric types
        num_metrics = len(self.windows)
        if num_metrics == 0:
            logger.warning("No metrics to graph")
            return output_path
        
        fig, axes = plt.subplots(num_metrics, 2, figsize=(15, 5 * num_metrics))
        if num_metrics == 1:
            axes = axes.reshape(1, -1)
        
        for idx, (metric_type, window) in enumerate(self.windows.items()):
            if not window:
                continue
            
            window_list = list(window)
            
            # Histogram
            ax1 = axes[idx, 0]
            ax1.hist(window_list, bins=50, edgecolor='black', alpha=0.7)
            ax1.set_title(f'{metric_type.upper()} Latency Distribution')
            ax1.set_xlabel('Latency (ms)')
            ax1.set_ylabel('Frequency')
            
            # Add percentile lines
            percentiles = self.calculate_percentiles(window_list)
            for p, value in percentiles.items():
                ax1.axvline(value, color='red', linestyle='--', alpha=0.5, label=f'P{p}: {value:.2f}ms')
            ax1.legend()
            
            # Time series
            ax2 = axes[idx, 1]
            if metric_type in self.time_series:
                ts_data = self.time_series[metric_type][-1000:]  # Last 1000 points
                if ts_data:
                    timestamps = [datetime.fromisoformat(d['timestamp']) for d in ts_data]
                    latencies = [d['latency'] for d in ts_data]
                    ax2.plot(timestamps, latencies, alpha=0.7)
                    ax2.set_title(f'{metric_type.upper()} Latency Over Time')
                    ax2.set_xlabel('Time')
                    ax2.set_ylabel('Latency (ms)')
                    ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Latency graph saved to {output_path}")
        return output_path
    
    def export_metrics(self, output_path: str = None) -> str:
        """
        Export metrics to JSON and CSV files.
        
        Args:
            output_path: Base path for output files
            
        Returns:
            Path to the JSON file
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'benchmarks/results/latency_metrics_{timestamp}'
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Export JSON
        json_path = f'{output_path}.json'
        metrics = self.get_current_metrics()
        
        # Add detailed breakdown
        metrics['detailed'] = {}
        for metric_type, data in self.metrics.items():
            if data['histogram']:
                metrics['detailed'][metric_type] = {
                    'histogram': data['histogram'][-1000:],  # Last 1000 points
                    'percentiles': self.calculate_percentiles(data['histogram']),
                    'statistics': {
                        'mean': statistics.mean(data['histogram']),
                        'median': statistics.median(data['histogram']),
                        'stdev': statistics.stdev(data['histogram']) if len(data['histogram']) > 1 else 0,
                    }
                }
        
        with open(json_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Export CSV for each metric type
        for metric_type, ts_data in self.time_series.items():
            if not ts_data:
                continue
            
            csv_path = f'{output_path}_{metric_type}.csv'
            df = pd.DataFrame(ts_data)
            df.to_csv(csv_path, index=False)
        
        logger.info(f"Metrics exported to {json_path}")
        return json_path
    
    def print_summary(self):
        """Print a summary of current metrics"""
        metrics = self.get_current_metrics()
        
        print("\n" + "="*60)
        print("LATENCY METRICS SUMMARY")
        print("="*60)
        print(f"Timestamp: {metrics['timestamp']}")
        print(f"Elapsed Time: {metrics['elapsed_seconds']:.2f} seconds")
        print()
        
        for metric_type, data in metrics['metrics'].items():
            print(f"{metric_type.upper()} Metrics:")
            print(f"  Total Requests: {data['count']:,}")
            print(f"  Rate: {data['rate_per_second']:.2f} req/s")
            print(f"  Mean: {data['mean']:.2f} ms")
            print(f"  Min: {data['min']:.2f} ms")
            print(f"  Max: {data['max']:.2f} ms")
            
            for p_name, p_value in data['percentiles'].items():
                print(f"  {p_name.upper()}: {p_value:.2f} ms")
            print()
        
        print("="*60 + "\n")
    
    async def start_server(self, port: int = 9091):
        """Start the metrics HTTP server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', port)
        await site.start()
        logger.info(f"Metrics server started on http://localhost:{port}")
        logger.info(f"  Prometheus metrics: http://localhost:{port}/metrics")
        logger.info(f"  JSON metrics: http://localhost:{port}/metrics/json")
        logger.info(f"  Latency graph: http://localhost:{port}/metrics/graph")


async def simulate_traffic(tracker: LatencyTracker):
    """Simulate traffic for testing the tracker"""
    import random
    
    endpoints = ['/api/v1/chat', '/api/v1/conversations', '/api/v1/auth']
    models = ['gpt-4', 'claude-3-opus', 'llama-3-70b']
    
    logger.info("Starting traffic simulation...")
    
    for i in range(1000):
        # Simulate API latency
        latency = random.gauss(150, 50)  # Mean 150ms, stddev 50ms
        latency = max(10, min(1000, latency))  # Clamp between 10-1000ms
        
        tracker.record_latency('api', latency, {
            'endpoint': random.choice(endpoints),
            'method': random.choice(['GET', 'POST']),
            'model': random.choice(models),
            'status': '200' if random.random() > 0.05 else '500'
        })
        
        # Simulate WebSocket latency
        if random.random() > 0.5:
            ws_latency = random.gauss(50, 20)
            ws_latency = max(5, min(500, ws_latency))
            tracker.record_latency('websocket', ws_latency, {
                'message_type': random.choice(['chat', 'ping', 'stream']),
                'model': random.choice(models)
            })
        
        # Simulate cache latency
        if random.random() > 0.7:
            cache_latency = random.gauss(5, 2) if random.random() > 0.3 else random.gauss(100, 30)
            cache_latency = max(1, min(200, cache_latency))
            tracker.record_latency('cache', cache_latency, {
                'operation': random.choice(['get', 'set']),
                'hit': 'true' if random.random() > 0.3 else 'false'
            })
        
        # Simulate model inference latency
        if random.random() > 0.6:
            model = random.choice(models)
            model_latency = {
                'gpt-4': random.gauss(800, 200),
                'claude-3-opus': random.gauss(700, 150),
                'llama-3-70b': random.gauss(600, 100),
            }[model]
            model_latency = max(100, min(2000, model_latency))
            tracker.record_latency('model', model_latency, {
                'model': model,
                'provider': model.split('-')[0]
            })
        
        await asyncio.sleep(0.01)  # 100 requests per second
        
        if (i + 1) % 100 == 0:
            logger.info(f"Simulated {i + 1} requests")
    
    logger.info("Traffic simulation completed")


async def main():
    """Main function for standalone testing"""
    tracker = LatencyTracker()
    
    # Start metrics server
    await tracker.start_server()
    
    # Run simulation
    await simulate_traffic(tracker)
    
    # Print summary
    tracker.print_summary()
    
    # Generate graph
    tracker.generate_latency_graph()
    
    # Export metrics
    tracker.export_metrics()
    
    # Keep server running
    logger.info("Press Ctrl+C to stop the server")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    asyncio.run(main())