#!/usr/bin/env python3
"""
Cost analyzer for tracking and validating AI model API costs.
Validates the 30% cost reduction claim through semantic caching.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pricing data (as of 2024)
PRICING = {
    'openai': {
        'gpt-4': {
            'input': 0.03,  # per 1K tokens
            'output': 0.06,  # per 1K tokens
        },
        'gpt-4-turbo': {
            'input': 0.01,
            'output': 0.03,
        },
        'gpt-3.5-turbo': {
            'input': 0.0005,
            'output': 0.0015,
        },
    },
    'anthropic': {
        'claude-3-opus': {
            'input': 0.015,
            'output': 0.075,
        },
        'claude-3-sonnet': {
            'input': 0.003,
            'output': 0.015,
        },
        'claude-3-haiku': {
            'input': 0.00025,
            'output': 0.00125,
        },
    },
    'meta': {
        'llama-3-70b': {
            'input': 0.0008,
            'output': 0.0008,
        },
        'llama-3-8b': {
            'input': 0.0002,
            'output': 0.0002,
        },
    },
}


@dataclass
class APICall:
    """Represents a single API call"""
    timestamp: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached: bool
    cache_key: Optional[str]
    response_time_ms: float
    tenant_id: str
    conversation_id: str
    message_id: str


@dataclass
class CostReport:
    """Cost analysis report"""
    total_calls: int
    cached_calls: int
    cache_hit_rate: float
    total_cost: float
    cached_cost: float
    savings: float
    savings_percentage: float
    cost_by_model: Dict[str, float]
    cost_by_provider: Dict[str, float]
    cost_by_tenant: Dict[str, float]
    average_cost_per_call: float
    projected_monthly_cost: float
    projected_monthly_savings: float


class CostAnalyzer:
    """Analyze API costs and cache effectiveness"""
    
    def __init__(self):
        """Initialize cost analyzer"""
        self.api_calls: List[APICall] = []
        self.cache_store: Dict[str, APICall] = {}
        self.start_time = time.time()
        
        # Metrics
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.cached_input_tokens = 0
        self.cached_output_tokens = 0
        
        # Cost tracking
        self.costs_by_model = defaultdict(float)
        self.costs_by_provider = defaultdict(float)
        self.costs_by_tenant = defaultdict(float)
        self.costs_over_time = []
        
        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_savings = 0.0
    
    def record_api_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False,
        cache_key: Optional[str] = None,
        response_time_ms: float = 0,
        tenant_id: str = 'default',
        conversation_id: str = '',
        message_id: str = ''
    ) -> float:
        """
        Record an API call and calculate its cost.
        
        Args:
            model: Model name (e.g., 'gpt-4', 'claude-3-opus')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cached: Whether this was served from cache
            cache_key: Cache key if applicable
            response_time_ms: Response time in milliseconds
            tenant_id: Tenant identifier
            conversation_id: Conversation identifier
            message_id: Message identifier
            
        Returns:
            Cost of the API call
        """
        provider = self._get_provider(model)
        
        api_call = APICall(
            timestamp=datetime.now().isoformat(),
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached=cached,
            cache_key=cache_key,
            response_time_ms=response_time_ms,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id
        )
        
        self.api_calls.append(api_call)
        
        if cached and cache_key:
            # Cache hit - no API cost
            self.cache_hits += 1
            self.cached_input_tokens += input_tokens
            self.cached_output_tokens += output_tokens
            
            # Calculate what we saved
            original_cost = self._calculate_cost(model, input_tokens, output_tokens)
            self.cache_savings += original_cost
            
            # Store in cache for future reference
            if cache_key not in self.cache_store:
                self.cache_store[cache_key] = api_call
            
            return 0.0  # No cost for cached response
        else:
            # Cache miss or no caching
            self.cache_misses += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
            # Calculate actual cost
            cost = self._calculate_cost(model, input_tokens, output_tokens)
            
            # Track costs
            self.costs_by_model[model] += cost
            self.costs_by_provider[provider] += cost
            self.costs_by_tenant[tenant_id] += cost
            
            # Time series data
            self.costs_over_time.append({
                'timestamp': api_call.timestamp,
                'cost': cost,
                'cumulative_cost': sum(c['cost'] for c in self.costs_over_time) + cost,
                'model': model,
                'cached': cached
            })
            
            # Store in cache for future use
            if cache_key:
                self.cache_store[cache_key] = api_call
            
            return cost
    
    def _get_provider(self, model: str) -> str:
        """Determine provider from model name"""
        if 'gpt' in model.lower():
            return 'openai'
        elif 'claude' in model.lower():
            return 'anthropic'
        elif 'llama' in model.lower():
            return 'meta'
        else:
            return 'unknown'
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given model and token counts"""
        provider = self._get_provider(model)
        
        # Find pricing info
        pricing_info = None
        if provider in PRICING:
            for model_key in PRICING[provider]:
                if model_key in model.lower():
                    pricing_info = PRICING[provider][model_key]
                    break
        
        if not pricing_info:
            # Default pricing if model not found
            logger.warning(f"No pricing info for model {model}, using default")
            pricing_info = {'input': 0.01, 'output': 0.03}
        
        # Calculate cost (prices are per 1K tokens)
        input_cost = (input_tokens / 1000) * pricing_info['input']
        output_cost = (output_tokens / 1000) * pricing_info['output']
        
        return input_cost + output_cost
    
    def simulate_cache_scenario(self, cache_hit_rate: float = 0.3) -> CostReport:
        """
        Simulate a cache scenario with given hit rate.
        
        Args:
            cache_hit_rate: Target cache hit rate (0.3 = 30%)
            
        Returns:
            Cost report with simulated cache performance
        """
        import random
        
        simulated_calls = []
        simulated_cost_with_cache = 0.0
        simulated_cost_without_cache = 0.0
        
        for call in self.api_calls:
            # Determine if this would be cached
            would_cache = random.random() < cache_hit_rate
            
            # Calculate costs
            actual_cost = self._calculate_cost(
                call.model,
                call.input_tokens,
                call.output_tokens
            )
            
            simulated_cost_without_cache += actual_cost
            
            if would_cache:
                # Cached - no cost
                simulated_cost_with_cache += 0
            else:
                # Not cached - full cost
                simulated_cost_with_cache += actual_cost
        
        savings = simulated_cost_without_cache - simulated_cost_with_cache
        savings_percentage = (savings / simulated_cost_without_cache * 100) if simulated_cost_without_cache > 0 else 0
        
        logger.info(f"Simulation: {cache_hit_rate*100:.1f}% cache hit rate -> {savings_percentage:.1f}% cost reduction")
        
        return savings_percentage
    
    def generate_report(self) -> CostReport:
        """Generate comprehensive cost analysis report"""
        total_calls = len(self.api_calls)
        cached_calls = sum(1 for call in self.api_calls if call.cached)
        cache_hit_rate = cached_calls / total_calls if total_calls > 0 else 0
        
        # Calculate total costs
        total_cost = sum(self.costs_by_model.values())
        
        # Calculate what the cost would have been without cache
        total_cost_without_cache = total_cost + self.cache_savings
        
        # Calculate savings
        savings = self.cache_savings
        savings_percentage = (savings / total_cost_without_cache * 100) if total_cost_without_cache > 0 else 0
        
        # Average cost per call
        avg_cost = total_cost / total_calls if total_calls > 0 else 0
        
        # Project monthly costs (assuming current rate)
        elapsed_hours = (time.time() - self.start_time) / 3600
        if elapsed_hours > 0:
            calls_per_hour = total_calls / elapsed_hours
            monthly_calls = calls_per_hour * 24 * 30
            projected_monthly_cost = avg_cost * monthly_calls
            projected_monthly_savings = (savings / total_calls * monthly_calls) if total_calls > 0 else 0
        else:
            projected_monthly_cost = 0
            projected_monthly_savings = 0
        
        report = CostReport(
            total_calls=total_calls,
            cached_calls=cached_calls,
            cache_hit_rate=cache_hit_rate,
            total_cost=total_cost,
            cached_cost=0.0,  # Cached calls have no cost
            savings=savings,
            savings_percentage=savings_percentage,
            cost_by_model=dict(self.costs_by_model),
            cost_by_provider=dict(self.costs_by_provider),
            cost_by_tenant=dict(self.costs_by_tenant),
            average_cost_per_call=avg_cost,
            projected_monthly_cost=projected_monthly_cost,
            projected_monthly_savings=projected_monthly_savings
        )
        
        return report
    
    def print_report(self, report: Optional[CostReport] = None):
        """Print formatted cost report"""
        if report is None:
            report = self.generate_report()
        
        print("\n" + "="*60)
        print("COST ANALYSIS REPORT")
        print("="*60)
        
        print(f"\nAPI Calls:")
        print(f"  Total Calls: {report.total_calls:,}")
        print(f"  Cached Calls: {report.cached_calls:,}")
        print(f"  Cache Hit Rate: {report.cache_hit_rate*100:.2f}%")
        
        print(f"\nCost Analysis:")
        print(f"  Total Cost: ${report.total_cost:.4f}")
        print(f"  Cache Savings: ${report.savings:.4f}")
        print(f"  Savings Percentage: {report.savings_percentage:.2f}%")
        print(f"  Average Cost per Call: ${report.average_cost_per_call:.6f}")
        
        print(f"\nCost by Model:")
        for model, cost in sorted(report.cost_by_model.items(), key=lambda x: x[1], reverse=True):
            print(f"  {model}: ${cost:.4f}")
        
        print(f"\nCost by Provider:")
        for provider, cost in sorted(report.cost_by_provider.items(), key=lambda x: x[1], reverse=True):
            print(f"  {provider}: ${cost:.4f}")
        
        print(f"\nProjections (30-day):")
        print(f"  Projected Monthly Cost: ${report.projected_monthly_cost:.2f}")
        print(f"  Projected Monthly Savings: ${report.projected_monthly_savings:.2f}")
        
        # Validate 30% cost reduction claim
        print(f"\n{'='*60}")
        if report.savings_percentage >= 30:
            print(f"VALIDATION: PASS - Cost reduction of {report.savings_percentage:.1f}% exceeds 30% target")
        else:
            print(f"VALIDATION: FAIL - Cost reduction of {report.savings_percentage:.1f}% below 30% target")
        print("="*60 + "\n")
    
    def generate_visualizations(self, output_dir: str = 'benchmarks/results'):
        """Generate cost analysis visualizations"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Set style
        sns.set_style("whitegrid")
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. Cost over time
        if self.costs_over_time:
            df_time = pd.DataFrame(self.costs_over_time)
            df_time['timestamp'] = pd.to_datetime(df_time['timestamp'])
            
            ax = axes[0, 0]
            ax.plot(df_time['timestamp'], df_time['cumulative_cost'], marker='o', markersize=2)
            ax.set_title('Cumulative Cost Over Time')
            ax.set_xlabel('Time')
            ax.set_ylabel('Cumulative Cost ($)')
            ax.tick_params(axis='x', rotation=45)
        
        # 2. Cost by model (pie chart)
        if self.costs_by_model:
            ax = axes[0, 1]
            models = list(self.costs_by_model.keys())
            costs = list(self.costs_by_model.values())
            ax.pie(costs, labels=models, autopct='%1.1f%%')
            ax.set_title('Cost Distribution by Model')
        
        # 3. Cache hit rate over time
        if self.api_calls:
            ax = axes[0, 2]
            
            # Calculate rolling cache hit rate
            window_size = min(100, len(self.api_calls))
            cache_rates = []
            timestamps = []
            
            for i in range(window_size, len(self.api_calls) + 1):
                window = self.api_calls[i-window_size:i]
                hits = sum(1 for call in window if call.cached)
                rate = hits / window_size
                cache_rates.append(rate * 100)
                timestamps.append(datetime.fromisoformat(self.api_calls[i-1].timestamp))
            
            if cache_rates:
                ax.plot(timestamps, cache_rates)
                ax.axhline(y=30, color='r', linestyle='--', label='30% Target')
                ax.set_title('Cache Hit Rate (Rolling Window)')
                ax.set_xlabel('Time')
                ax.set_ylabel('Cache Hit Rate (%)')
                ax.legend()
                ax.tick_params(axis='x', rotation=45)
        
        # 4. Token usage distribution
        if self.api_calls:
            ax = axes[1, 0]
            input_tokens = [call.input_tokens for call in self.api_calls]
            output_tokens = [call.output_tokens for call in self.api_calls]
            
            ax.hist([input_tokens, output_tokens], label=['Input', 'Output'], bins=30, alpha=0.7)
            ax.set_title('Token Usage Distribution')
            ax.set_xlabel('Tokens')
            ax.set_ylabel('Frequency')
            ax.legend()
        
        # 5. Response time vs cost
        if self.api_calls:
            ax = axes[1, 1]
            response_times = [call.response_time_ms for call in self.api_calls if not call.cached]
            costs = []
            for call in self.api_calls:
                if not call.cached:
                    cost = self._calculate_cost(call.model, call.input_tokens, call.output_tokens)
                    costs.append(cost)
            
            if response_times and costs:
                ax.scatter(response_times, costs, alpha=0.5)
                ax.set_title('Response Time vs Cost')
                ax.set_xlabel('Response Time (ms)')
                ax.set_ylabel('Cost ($)')
        
        # 6. Savings breakdown
        report = self.generate_report()
        ax = axes[1, 2]
        
        categories = ['Without Cache', 'With Cache', 'Savings']
        values = [
            report.total_cost + report.savings,
            report.total_cost,
            report.savings
        ]
        colors = ['red', 'green', 'blue']
        
        bars = ax.bar(categories, values, color=colors)
        ax.set_title('Cost Comparison')
        ax.set_ylabel('Cost ($)')
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'${value:.4f}',
                   ha='center', va='bottom')
        
        # Add savings percentage
        if values[0] > 0:
            savings_pct = (values[2] / values[0]) * 100
            ax.text(0.5, 0.95, f'Savings: {savings_pct:.1f}%',
                   transform=ax.transAxes,
                   ha='center', va='top',
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))
        
        plt.tight_layout()
        
        # Save figure
        output_path = Path(output_dir) / 'cost_analysis.png'
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Visualizations saved to {output_path}")
    
    def export_data(self, output_path: str = None) -> str:
        """Export cost analysis data to JSON and CSV"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'benchmarks/results/cost_analysis_{timestamp}'
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Export report as JSON
        report = self.generate_report()
        json_path = f'{output_path}.json'
        
        report_dict = asdict(report)
        report_dict['timestamp'] = datetime.now().isoformat()
        report_dict['total_input_tokens'] = self.total_input_tokens
        report_dict['total_output_tokens'] = self.total_output_tokens
        report_dict['cached_input_tokens'] = self.cached_input_tokens
        report_dict['cached_output_tokens'] = self.cached_output_tokens
        
        with open(json_path, 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        # Export API calls as CSV
        if self.api_calls:
            csv_path = f'{output_path}_calls.csv'
            df = pd.DataFrame([asdict(call) for call in self.api_calls])
            df.to_csv(csv_path, index=False)
            logger.info(f"API calls exported to {csv_path}")
        
        logger.info(f"Cost analysis exported to {json_path}")
        return json_path


def simulate_realistic_load(analyzer: CostAnalyzer, duration_minutes: int = 10):
    """Simulate realistic API load for testing"""
    import random
    import hashlib
    
    models = [
        ('gpt-4', 0.2),
        ('gpt-3.5-turbo', 0.4),
        ('claude-3-opus', 0.15),
        ('claude-3-sonnet', 0.15),
        ('llama-3-70b', 0.1),
    ]
    
    tenants = ['tenant-1', 'tenant-2', 'tenant-3']
    
    # Common prompts that would be cached
    common_prompts = [
        "What is machine learning?",
        "Explain Docker containers",
        "What are microservices?",
        "How does OAuth 2.0 work?",
        "What is the CAP theorem?",
    ]
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    request_count = 0
    cache_store = {}  # Simple cache simulation
    
    logger.info(f"Starting {duration_minutes} minute simulation...")
    
    while time.time() < end_time:
        # Select model based on weights
        model = random.choices(
            [m[0] for m in models],
            weights=[m[1] for m in models]
        )[0]
        
        # Generate prompt
        if random.random() < 0.3:  # 30% chance of common prompt
            prompt = random.choice(common_prompts)
            cache_key = hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()
        else:
            prompt = f"Random prompt {random.randint(1000, 9999)}"
            cache_key = hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()
        
        # Token counts (realistic ranges)
        input_tokens = random.randint(50, 500)
        output_tokens = random.randint(100, 1500)
        
        # Check cache
        cached = cache_key in cache_store
        if not cached and random.random() < 0.3:  # Store in cache
            cache_store[cache_key] = True
        
        # Response time
        if cached:
            response_time = random.gauss(50, 10)  # Fast cache response
        else:
            response_time = random.gauss(500, 150)  # Normal API response
        
        # Record the call
        analyzer.record_api_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached=cached,
            cache_key=cache_key,
            response_time_ms=max(10, response_time),
            tenant_id=random.choice(tenants),
            conversation_id=f"conv_{random.randint(1, 100)}",
            message_id=f"msg_{request_count}"
        )
        
        request_count += 1
        
        # Random delay between requests
        time.sleep(random.uniform(0.1, 0.5))
        
        if request_count % 100 == 0:
            logger.info(f"Processed {request_count} requests...")
    
    logger.info(f"Simulation complete. Processed {request_count} requests.")


def main():
    """Main function for testing"""
    analyzer = CostAnalyzer()
    
    # Run simulation
    simulate_realistic_load(analyzer, duration_minutes=2)
    
    # Generate and print report
    report = analyzer.generate_report()
    analyzer.print_report(report)
    
    # Test different cache scenarios
    print("\nCache Scenario Analysis:")
    for hit_rate in [0.1, 0.2, 0.3, 0.4, 0.5]:
        savings_pct = analyzer.simulate_cache_scenario(hit_rate)
    
    # Generate visualizations
    analyzer.generate_visualizations()
    
    # Export data
    analyzer.export_data()


if __name__ == '__main__':
    main()