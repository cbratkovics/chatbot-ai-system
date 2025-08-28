#!/usr/bin/env python3
"""
Orchestrate all benchmarks and generate comprehensive report.
Validates performance claims and generates evidence.
"""

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import argparse

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from benchmarks.performance.latency_tracker import LatencyTracker
from benchmarks.performance.cost_analyzer import CostAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Orchestrate and run all benchmarks"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize benchmark runner.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self.load_config(config_path)
        self.results = {}
        self.start_time = None
        self.end_time = None
        
        # Ensure results directory exists
        self.results_dir = Path('benchmarks/results')
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize trackers
        self.latency_tracker = LatencyTracker()
        self.cost_analyzer = CostAnalyzer()
    
    def load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from file or use defaults"""
        default_config = {
            'k6': {
                'websocket_test': {
                    'enabled': True,
                    'script': 'benchmarks/load_tests/k6_websocket_test.js',
                    'duration': '5m',
                    'vus': 100,
                },
                'api_test': {
                    'enabled': True,
                    'script': 'benchmarks/load_tests/k6_api_test.js',
                    'duration': '5m',
                    'vus': 100,
                },
            },
            'locust': {
                'enabled': True,
                'script': 'benchmarks/load_tests/locust_scenarios.py',
                'users': 100,
                'spawn_rate': 10,
                'run_time': '5m',
            },
            'performance_targets': {
                'p95_latency_ms': 200,
                'p99_latency_ms': 500,
                'error_rate': 0.01,
                'cache_hit_rate': 0.3,
                'cost_reduction': 0.3,
                'concurrent_users': 100,
            },
            'baseline_comparison': {
                'enabled': True,
                'baseline_file': 'benchmarks/results/baseline.json',
                'tolerance': 0.1,  # 10% tolerance
            },
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                # Merge user config with defaults
                return {**default_config, **user_config}
        
        return default_config
    
    def check_dependencies(self) -> bool:
        """Check if required tools are installed"""
        dependencies = {
            'k6': 'k6 version',
            'locust': 'locust --version',
            'docker': 'docker --version',
        }
        
        missing = []
        for tool, command in dependencies.items():
            try:
                subprocess.run(
                    command.split(),
                    capture_output=True,
                    check=True
                )
                logger.info(f"Found {tool}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing.append(tool)
                logger.warning(f"Missing {tool}")
        
        if missing:
            logger.error(f"Missing dependencies: {', '.join(missing)}")
            logger.error("Please install missing tools before running benchmarks")
            return False
        
        return True
    
    def start_services(self) -> bool:
        """Start required services using docker-compose"""
        logger.info("Starting services...")
        
        compose_file = Path('config/docker/compose/docker-compose.yml')
        if not compose_file.exists():
            logger.warning("config/docker/compose/docker-compose.yml not found, skipping service startup")
            return True
        
        try:
            subprocess.run(
                ['docker-compose', 'up', '-d', 'postgres', 'redis'],
                check=True,
                capture_output=True
            )
            logger.info("Services started successfully")
            
            # Wait for services to be ready
            time.sleep(5)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start services: {e}")
            return False
    
    def run_k6_test(self, test_name: str, config: Dict) -> Dict:
        """Run a k6 test and collect results"""
        logger.info(f"Running k6 test: {test_name}")
        
        script_path = config['script']
        if not Path(script_path).exists():
            logger.error(f"k6 script not found: {script_path}")
            return {'error': 'Script not found'}
        
        # Build k6 command
        cmd = [
            'k6', 'run',
            '--out', 'json=benchmarks/results/k6_metrics.json',
            '--summary-export', f'benchmarks/results/{test_name}_summary.json',
        ]
        
        # Add test parameters
        if 'vus' in config:
            cmd.extend(['--vus', str(config['vus'])])
        if 'duration' in config:
            cmd.extend(['--duration', config['duration']])
        
        # Add environment variables
        env_vars = {
            'WS_URL': 'ws://localhost:8000/ws',
            'API_URL': 'http://localhost:8000',
        }
        
        cmd.append(script_path)
        
        try:
            # Run k6 test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env={**env_vars}
            )
            
            if result.returncode != 0:
                logger.error(f"k6 test failed: {result.stderr}")
                return {'error': result.stderr}
            
            # Load and parse results
            summary_file = f'benchmarks/results/{test_name}_summary.json'
            if Path(summary_file).exists():
                with open(summary_file, 'r') as f:
                    summary = json.load(f)
                
                # Extract key metrics
                metrics = self.extract_k6_metrics(summary)
                logger.info(f"k6 test {test_name} completed successfully")
                return metrics
            else:
                logger.error(f"Summary file not found: {summary_file}")
                return {'error': 'Summary file not found'}
                
        except Exception as e:
            logger.error(f"Error running k6 test: {e}")
            return {'error': str(e)}
    
    def extract_k6_metrics(self, summary: Dict) -> Dict:
        """Extract key metrics from k6 summary"""
        metrics = {}
        
        # Extract custom metrics if available
        if 'metrics' in summary:
            for metric_name, metric_data in summary['metrics'].items():
                if 'values' in metric_data:
                    values = metric_data['values']
                    
                    # Extract percentiles
                    if 'p(50)' in values:
                        metrics[f"{metric_name}_p50"] = values['p(50)']
                    if 'p(95)' in values:
                        metrics[f"{metric_name}_p95"] = values['p(95)']
                    if 'p(99)' in values:
                        metrics[f"{metric_name}_p99"] = values['p(99)']
                    
                    # Extract other values
                    if 'avg' in values:
                        metrics[f"{metric_name}_avg"] = values['avg']
                    if 'rate' in values:
                        metrics[f"{metric_name}_rate"] = values['rate']
                    if 'count' in values:
                        metrics[f"{metric_name}_count"] = values['count']
        
        # Extract threshold results
        if 'thresholds' in summary:
            metrics['thresholds'] = {}
            for threshold_name, threshold_data in summary['thresholds'].items():
                metrics['thresholds'][threshold_name] = threshold_data.get('ok', False)
        
        return metrics
    
    def run_locust_test(self, config: Dict) -> Dict:
        """Run Locust test and collect results"""
        logger.info("Running Locust test")
        
        script_path = config['script']
        if not Path(script_path).exists():
            logger.error(f"Locust script not found: {script_path}")
            return {'error': 'Script not found'}
        
        # Build Locust command
        cmd = [
            'locust',
            '-f', script_path,
            '--headless',
            '--users', str(config['users']),
            '--spawn-rate', str(config['spawn_rate']),
            '--run-time', config['run_time'],
            '--host', 'http://localhost:8000',
            '--html', 'benchmarks/results/locust_report.html',
            '--csv', 'benchmarks/results/locust',
        ]
        
        try:
            # Run Locust test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Locust test failed: {result.stderr}")
                return {'error': result.stderr}
            
            # Load results
            results_file = 'benchmarks/results/locust_results.json'
            if Path(results_file).exists():
                with open(results_file, 'r') as f:
                    metrics = json.load(f)
                
                logger.info("Locust test completed successfully")
                return metrics
            else:
                logger.warning("Locust results file not found")
                return {'warning': 'Results file not found'}
                
        except Exception as e:
            logger.error(f"Error running Locust test: {e}")
            return {'error': str(e)}
    
    def validate_performance(self, results: Dict) -> Dict:
        """Validate performance against targets"""
        targets = self.config['performance_targets']
        validation = {
            'passed': [],
            'failed': [],
            'warnings': [],
        }
        
        # Check P95 latency
        if 'k6_api' in results:
            api_metrics = results['k6_api']
            
            # Check API latency
            if 'api_latency_p95' in api_metrics:
                p95 = api_metrics['api_latency_p95']
                target = targets['p95_latency_ms']
                if p95 <= target:
                    validation['passed'].append(f"P95 latency: {p95:.2f}ms <= {target}ms")
                else:
                    validation['failed'].append(f"P95 latency: {p95:.2f}ms > {target}ms")
            
            # Check concurrent users
            if 'vus_max_count' in api_metrics:
                max_users = api_metrics['vus_max_count']
                target = targets['concurrent_users']
                if max_users >= target:
                    validation['passed'].append(f"Concurrent users: {max_users} >= {target}")
                else:
                    validation['failed'].append(f"Concurrent users: {max_users} < {target}")
        
        # Check cache performance
        if 'locust' in results:
            locust_metrics = results['locust']
            
            # Check cache hit rate
            if 'cache_hit_rate' in locust_metrics:
                hit_rate = locust_metrics['cache_hit_rate']
                target = targets['cache_hit_rate']
                if hit_rate >= target:
                    validation['passed'].append(f"Cache hit rate: {hit_rate*100:.1f}% >= {target*100}%")
                else:
                    validation['failed'].append(f"Cache hit rate: {hit_rate*100:.1f}% < {target*100}%")
            
            # Check cost reduction
            if 'cost_reduction_percentage' in locust_metrics:
                reduction = locust_metrics['cost_reduction_percentage']
                target = targets['cost_reduction'] * 100
                if reduction >= target:
                    validation['passed'].append(f"Cost reduction: {reduction:.1f}% >= {target}%")
                else:
                    validation['failed'].append(f"Cost reduction: {reduction:.1f}% < {target}%")
        
        # Overall pass/fail
        validation['overall'] = len(validation['failed']) == 0
        
        return validation
    
    def compare_with_baseline(self, results: Dict) -> Dict:
        """Compare results with baseline"""
        if not self.config['baseline_comparison']['enabled']:
            return {'skipped': True}
        
        baseline_file = self.config['baseline_comparison']['baseline_file']
        if not Path(baseline_file).exists():
            logger.warning(f"Baseline file not found: {baseline_file}")
            return {'error': 'Baseline not found'}
        
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        
        tolerance = self.config['baseline_comparison']['tolerance']
        comparison = {
            'improvements': [],
            'regressions': [],
            'stable': [],
        }
        
        # Compare key metrics
        metrics_to_compare = [
            ('k6_api.api_latency_p95', 'API P95 Latency', False),  # Lower is better
            ('k6_websocket.ws_message_latency_p95', 'WebSocket P95 Latency', False),
            ('locust.cache_hit_rate', 'Cache Hit Rate', True),  # Higher is better
            ('locust.cost_reduction_percentage', 'Cost Reduction', True),
        ]
        
        for metric_path, metric_name, higher_better in metrics_to_compare:
            # Navigate nested dict
            current_value = results
            baseline_value = baseline.get('results', {})
            
            for key in metric_path.split('.'):
                current_value = current_value.get(key, None)
                baseline_value = baseline_value.get(key, None)
                if current_value is None or baseline_value is None:
                    break
            
            if current_value is not None and baseline_value is not None:
                diff = current_value - baseline_value
                pct_change = (diff / baseline_value) * 100 if baseline_value != 0 else 0
                
                if higher_better:
                    if pct_change > tolerance * 100:
                        comparison['improvements'].append(
                            f"{metric_name}: {current_value:.2f} (+{pct_change:.1f}%)"
                        )
                    elif pct_change < -tolerance * 100:
                        comparison['regressions'].append(
                            f"{metric_name}: {current_value:.2f} ({pct_change:.1f}%)"
                        )
                    else:
                        comparison['stable'].append(
                            f"{metric_name}: {current_value:.2f} ({pct_change:+.1f}%)"
                        )
                else:  # Lower is better
                    if pct_change < -tolerance * 100:
                        comparison['improvements'].append(
                            f"{metric_name}: {current_value:.2f} ({pct_change:.1f}%)"
                        )
                    elif pct_change > tolerance * 100:
                        comparison['regressions'].append(
                            f"{metric_name}: {current_value:.2f} (+{pct_change:.1f}%)"
                        )
                    else:
                        comparison['stable'].append(
                            f"{metric_name}: {current_value:.2f} ({pct_change:+.1f}%)"
                        )
        
        return comparison
    
    def generate_html_report(self, results: Dict, validation: Dict, comparison: Dict) -> str:
        """Generate HTML report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Benchmark Results - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .summary {{ background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .pass {{ color: #4CAF50; font-weight: bold; }}
        .fail {{ color: #f44336; font-weight: bold; }}
        .warning {{ color: #ff9800; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #4CAF50; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .metric-card {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
        .regression {{ border-left-color: #f44336; }}
        .improvement {{ border-left-color: #4CAF50; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Chatbot System - Benchmark Results</h1>
        <div class="summary">
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p><strong>Duration:</strong> {duration}</p>
            <p><strong>Overall Status:</strong> <span class="{overall_class}">{overall_status}</span></p>
        </div>
        
        <h2>Performance Validation</h2>
        <div class="metric-card {validation_class}">
            <h3>Passed Tests ({passed_count})</h3>
            <ul>{passed_tests}</ul>
            <h3>Failed Tests ({failed_count})</h3>
            <ul>{failed_tests}</ul>
        </div>
        
        <h2>Key Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Target</th>
                <th>Status</th>
            </tr>
            {metrics_table}
        </table>
        
        <h2>Baseline Comparison</h2>
        <div class="metric-card">
            {comparison_section}
        </div>
        
        <h2>Detailed Results</h2>
        <pre>{detailed_results}</pre>
    </div>
</body>
</html>
        """
        
        # Build HTML content
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        duration = f"{(self.end_time - self.start_time):.2f} seconds" if self.end_time else "N/A"
        
        overall_status = "PASSED" if validation['overall'] else "FAILED"
        overall_class = "pass" if validation['overall'] else "fail"
        validation_class = "improvement" if validation['overall'] else "regression"
        
        passed_tests = '\n'.join([f"<li>{test}</li>" for test in validation['passed']])
        failed_tests = '\n'.join([f"<li>{test}</li>" for test in validation['failed']])
        
        # Build metrics table
        metrics_rows = []
        targets = self.config['performance_targets']
        
        # Add rows for each metric
        if 'k6_api' in results and 'api_latency_p95' in results['k6_api']:
            value = results['k6_api']['api_latency_p95']
            target = targets['p95_latency_ms']
            status = "PASS" if value <= target else "FAIL"
            status_class = "pass" if value <= target else "fail"
            metrics_rows.append(
                f"<tr><td>P95 Latency</td><td>{value:.2f}ms</td><td>{target}ms</td>"
                f"<td class='{status_class}'>{status}</td></tr>"
            )
        
        metrics_table = '\n'.join(metrics_rows)
        
        # Build comparison section
        comparison_html = ""
        if 'error' not in comparison and 'skipped' not in comparison:
            if comparison.get('improvements'):
                comparison_html += "<h4>Improvements</h4><ul>"
                for imp in comparison['improvements']:
                    comparison_html += f"<li class='pass'>{imp}</li>"
                comparison_html += "</ul>"
            
            if comparison.get('regressions'):
                comparison_html += "<h4>Regressions</h4><ul>"
                for reg in comparison['regressions']:
                    comparison_html += f"<li class='fail'>{reg}</li>"
                comparison_html += "</ul>"
        else:
            comparison_html = "<p>Baseline comparison not available</p>"
        
        # Format HTML
        html = html_template.format(
            timestamp=timestamp,
            duration=duration,
            overall_status=overall_status,
            overall_class=overall_class,
            validation_class=validation_class,
            passed_count=len(validation['passed']),
            passed_tests=passed_tests or "<li>None</li>",
            failed_count=len(validation['failed']),
            failed_tests=failed_tests or "<li>None</li>",
            metrics_table=metrics_table,
            comparison_section=comparison_html,
            detailed_results=json.dumps(results, indent=2),
        )
        
        # Save HTML report
        report_path = self.results_dir / 'benchmark_report.html'
        with open(report_path, 'w') as f:
            f.write(html)
        
        logger.info(f"HTML report saved to {report_path}")
        return str(report_path)
    
    async def run(self) -> Dict:
        """Run all benchmarks"""
        self.start_time = time.time()
        
        logger.info("="*60)
        logger.info("Starting Benchmark Suite")
        logger.info("="*60)
        
        # Check dependencies
        if not self.check_dependencies():
            return {'error': 'Missing dependencies'}
        
        # Start services
        if not self.start_services():
            return {'error': 'Failed to start services'}
        
        # Give services time to stabilize
        logger.info("Waiting for services to stabilize...")
        await asyncio.sleep(5)
        
        # Run k6 tests
        if self.config['k6']['websocket_test']['enabled']:
            self.results['k6_websocket'] = self.run_k6_test(
                'k6_websocket',
                self.config['k6']['websocket_test']
            )
        
        if self.config['k6']['api_test']['enabled']:
            self.results['k6_api'] = self.run_k6_test(
                'k6_api',
                self.config['k6']['api_test']
            )
        
        # Run Locust test
        if self.config['locust']['enabled']:
            self.results['locust'] = self.run_locust_test(self.config['locust'])
        
        self.end_time = time.time()
        
        # Validate performance
        validation = self.validate_performance(self.results)
        
        # Compare with baseline
        comparison = self.compare_with_baseline(self.results)
        
        # Generate reports
        html_report = self.generate_html_report(self.results, validation, comparison)
        
        # Save complete results
        complete_results = {
            'timestamp': datetime.now().isoformat(),
            'duration': self.end_time - self.start_time,
            'results': self.results,
            'validation': validation,
            'comparison': comparison,
            'config': self.config,
        }
        
        results_file = self.results_dir / f'benchmark_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(results_file, 'w') as f:
            json.dump(complete_results, f, indent=2)
        
        # Save as latest for easy access
        latest_file = self.results_dir / 'latest.json'
        with open(latest_file, 'w') as f:
            json.dump(complete_results, f, indent=2)
        
        # Print summary
        self.print_summary(validation, comparison)
        
        logger.info(f"Results saved to {results_file}")
        logger.info(f"HTML report: {html_report}")
        
        return complete_results
    
    def print_summary(self, validation: Dict, comparison: Dict):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        # Validation results
        print("\nPerformance Validation:")
        if validation['passed']:
            print("  Passed:")
            for test in validation['passed']:
                print(f"    - {test}")
        
        if validation['failed']:
            print("  Failed:")
            for test in validation['failed']:
                print(f"    - {test}")
        
        # Baseline comparison
        if 'error' not in comparison and 'skipped' not in comparison:
            print("\nBaseline Comparison:")
            if comparison.get('improvements'):
                print("  Improvements:")
                for imp in comparison['improvements']:
                    print(f"    - {imp}")
            
            if comparison.get('regressions'):
                print("  Regressions:")
                for reg in comparison['regressions']:
                    print(f"    - {reg}")
        
        # Overall result
        print("\n" + "="*60)
        if validation['overall']:
            print("RESULT: ALL PERFORMANCE TARGETS MET")
        else:
            print("RESULT: PERFORMANCE TARGETS NOT MET")
            if not validation['overall']:
                print("\nAction Required:")
                print("- Review failed metrics")
                print("- Optimize identified bottlenecks")
                print("- Re-run benchmarks after fixes")
        print("="*60 + "\n")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run AI Chatbot System benchmarks')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--compare-baseline', action='store_true', 
                       help='Compare with baseline results')
    parser.add_argument('--save-baseline', action='store_true',
                       help='Save current results as baseline')
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(args.config)
    results = await runner.run()
    
    # Save as baseline if requested
    if args.save_baseline and 'error' not in results:
        baseline_file = Path('benchmarks/results/baseline.json')
        with open(baseline_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Baseline saved to {baseline_file}")
    
    # Exit with appropriate code
    if 'error' in results:
        sys.exit(1)
    elif results.get('validation', {}).get('overall', False):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())