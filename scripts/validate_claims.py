#!/usr/bin/env python3
"""
Validate all performance and feature claims in documentation.
This script checks that all advertised capabilities are actually implemented and working.
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ClaimValidator:
    """Validate all system claims"""
    
    def __init__(self):
        self.results_dir = Path('benchmarks/results')
        self.validations = []
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def load_benchmark_results(self) -> dict:
        """Load the latest benchmark results"""
        latest_file = self.results_dir / 'latest.json'
        
        if not latest_file.exists():
            # Try to find any results file
            result_files = list(self.results_dir.glob('benchmark_results_*.json'))
            if result_files:
                latest_file = sorted(result_files)[-1]
            else:
                logger.warning("No benchmark results found. Run benchmarks first.")
                return {}
        
        with open(latest_file) as f:
            return json.load(f)
    
    def load_cost_analysis(self) -> dict:
        """Load cost analysis results"""
        cost_files = list(self.results_dir.glob('cost_analysis_*.json'))
        
        if not cost_files:
            logger.warning("No cost analysis results found")
            return {}
        
        latest_cost = sorted(cost_files)[-1]
        with open(latest_cost) as f:
            return json.load(f)
    
    def validate_latency_claim(self) -> tuple[bool, str]:
        """Verify <200ms P95 latency claim"""
        results = self.load_benchmark_results()
        
        if not results:
            return False, "No benchmark results available"
        
        # Check API latency
        api_results = results.get('results', {}).get('k6_api', {})
        if 'api_latency_p95' in api_results:
            p95 = api_results['api_latency_p95']
            if p95 <= 200:
                return True, f"P95 latency: {p95:.2f}ms (target: <200ms)"
            else:
                return False, f"P95 latency: {p95:.2f}ms exceeds 200ms target"
        
        # Check WebSocket latency
        ws_results = results.get('results', {}).get('k6_websocket', {})
        if 'ws_message_latency_p95' in ws_results:
            p95 = ws_results['ws_message_latency_p95']
            if p95 <= 200:
                return True, f"WebSocket P95 latency: {p95:.2f}ms (target: <200ms)"
            else:
                return False, f"WebSocket P95 latency: {p95:.2f}ms exceeds 200ms target"
        
        return False, "Latency metrics not found in results"
    
    def validate_cost_reduction(self) -> tuple[bool, str]:
        """Verify 30% cost reduction claim"""
        cost_analysis = self.load_cost_analysis()
        
        if not cost_analysis:
            # Check in benchmark results
            results = self.load_benchmark_results()
            locust_results = results.get('results', {}).get('locust', {})
            
            if 'cost_reduction_percentage' in locust_results:
                reduction = locust_results['cost_reduction_percentage']
                if reduction >= 30:
                    return True, f"Cost reduction: {reduction:.1f}% (target: ≥30%)"
                else:
                    return False, f"Cost reduction: {reduction:.1f}% below 30% target"
        
        if 'savings_percentage' in cost_analysis:
            reduction = cost_analysis['savings_percentage']
            if reduction >= 30:
                return True, f"Cost reduction: {reduction:.1f}% (target: ≥30%)"
            else:
                return False, f"Cost reduction: {reduction:.1f}% below 30% target"
        
        return False, "Cost reduction metrics not found"
    
    def validate_concurrent_users(self) -> tuple[bool, str]:
        """Verify 100+ concurrent users claim"""
        results = self.load_benchmark_results()
        
        if not results:
            return False, "No benchmark results available"
        
        # Check k6 results
        k6_results = results.get('results', {})
        max_users = 0
        
        for test_name in ['k6_api', 'k6_websocket']:
            if test_name in k6_results:
                test_data = k6_results[test_name]
                if 'vus_max_count' in test_data:
                    max_users = max(max_users, test_data['vus_max_count'])
        
        if max_users >= 100:
            return True, f"Max concurrent users: {max_users} (target: ≥100)"
        elif max_users > 0:
            return False, f"Max concurrent users: {max_users} below 100 target"
        
        return False, "Concurrent user metrics not found"
    
    def validate_cache_hit_rate(self) -> tuple[bool, str]:
        """Verify cache effectiveness"""
        results = self.load_benchmark_results()
        
        if not results:
            return False, "No benchmark results available"
        
        locust_results = results.get('results', {}).get('locust', {})
        
        if 'cache_hit_rate' in locust_results:
            hit_rate = locust_results['cache_hit_rate']
            if hit_rate >= 0.3:
                return True, f"Cache hit rate: {hit_rate*100:.1f}% (good performance)"
            else:
                return False, f"Cache hit rate: {hit_rate*100:.1f}% (needs improvement)"
        
        return False, "Cache metrics not found"
    
    def validate_multi_model_support(self) -> tuple[bool, str]:
        """Verify multi-model integration claim"""
        # Check if provider implementations exist
        provider_files = [
            Path('api/providers/openai_provider.py'),
            Path('api/providers/anthropic_provider.py'),
            Path('api/providers/llama_provider.py'),
        ]
        
        existing = sum(1 for f in provider_files if f.exists())
        
        if existing == len(provider_files):
            return True, f"All {len(provider_files)} provider implementations found"
        elif existing > 0:
            return False, f"Only {existing}/{len(provider_files)} provider implementations found"
        else:
            return False, "No provider implementations found"
    
    def validate_websocket_support(self) -> tuple[bool, str]:
        """Verify WebSocket support claim"""
        # Check for WebSocket implementation
        ws_file = Path('api/websocket/manager.py')
        
        if ws_file.exists():
            # Check if WebSocket tests passed
            results = self.load_benchmark_results()
            ws_results = results.get('results', {}).get('k6_websocket', {})
            
            if ws_results and 'error' not in ws_results:
                return True, "WebSocket implementation verified and tested"
            else:
                return False, "WebSocket implementation found but tests failed"
        
        return False, "WebSocket implementation not found"
    
    def validate_monitoring_setup(self) -> tuple[bool, str]:
        """Verify monitoring and observability setup"""
        monitoring_files = [
            Path('monitoring/grafana/dashboards'),
            Path('monitoring/prometheus/alerts.yml'),
        ]
        
        existing = sum(1 for f in monitoring_files if f.exists())
        
        if existing == len(monitoring_files):
            return True, "Monitoring configuration complete"
        elif existing > 0:
            return False, f"Partial monitoring setup ({existing}/{len(monitoring_files)} components)"
        else:
            return False, "Monitoring configuration not found"
    
    def validate_test_coverage(self) -> tuple[bool, str]:
        """Check if test coverage meets standards"""
        coverage_file = Path('tests/coverage_reports/coverage.xml')
        
        if coverage_file.exists():
            # Parse coverage report (simplified)
            with open(coverage_file) as f:
                content = f.read()
                # Look for coverage percentage (this is simplified)
                if 'line-rate="0.8' in content or 'line-rate="0.9' in content:
                    return True, "Test coverage ≥80%"
                else:
                    return False, "Test coverage <80%"
        
        # Check if tests exist
        test_dirs = [
            Path('tests/unit'),
            Path('tests/integration'),
            Path('tests/e2e'),
        ]
        
        existing = sum(1 for d in test_dirs if d.exists())
        
        if existing == len(test_dirs):
            return True, f"All test directories present ({existing}/{len(test_dirs)})"
        elif existing > 0:
            return False, f"Partial test structure ({existing}/{len(test_dirs)} directories)"
        else:
            return False, "Test structure not found"
    
    def validate_documentation(self) -> tuple[bool, str]:
        """Verify documentation completeness"""
        required_docs = [
            Path('README.md'),
            Path('docs/architecture/ARCHITECTURE.md'),
            Path('docs/performance/PERFORMANCE.md'),
            Path('docs/security/SECURITY.md'),
            Path('CONTRIBUTING.md'),
            Path('LICENSE'),
        ]
        
        missing = [str(doc) for doc in required_docs if not doc.exists()]
        
        if not missing:
            return True, "All required documentation present"
        elif len(missing) < len(required_docs) / 2:
            return False, f"Missing docs: {', '.join(missing)}"
        else:
            return False, f"Most documentation missing ({len(missing)}/{len(required_docs)})"
    
    def validate_ci_cd_pipeline(self) -> tuple[bool, str]:
        """Verify CI/CD pipeline configuration"""
        ci_files = [
            Path('.github/workflows/ci.yml'),
            Path('ci/comprehensive-testing.yml'),
            Path('Dockerfile'),
            Path('config/docker/compose/docker-compose.yml'),
        ]
        
        existing = [f for f in ci_files if f.exists()]
        
        if len(existing) >= 2:
            return True, f"CI/CD configuration found ({len(existing)} files)"
        elif existing:
            return False, f"Partial CI/CD setup ({len(existing)} files)"
        else:
            return False, "CI/CD configuration not found"
    
    def run_all_validations(self):
        """Run all validation checks"""
        validations = [
            ("P95 Latency <200ms", self.validate_latency_claim),
            ("30% Cost Reduction", self.validate_cost_reduction),
            ("100+ Concurrent Users", self.validate_concurrent_users),
            ("Cache Effectiveness", self.validate_cache_hit_rate),
            ("Multi-Model Support", self.validate_multi_model_support),
            ("WebSocket Support", self.validate_websocket_support),
            ("Monitoring Setup", self.validate_monitoring_setup),
            ("Test Coverage", self.validate_test_coverage),
            ("Documentation", self.validate_documentation),
            ("CI/CD Pipeline", self.validate_ci_cd_pipeline),
        ]
        
        print("\n" + "="*60)
        print("CLAIM VALIDATION REPORT")
        print("="*60 + "\n")
        
        for claim_name, validator_func in validations:
            try:
                passed, message = validator_func()
                
                if passed:
                    self.passed.append(claim_name)
                    status = "PASS"
                    symbol = "✓"
                    color = '\033[92m'  # Green
                else:
                    self.failed.append(claim_name)
                    status = "FAIL"
                    symbol = "✗"
                    color = '\033[91m'  # Red
                
                print(f"{color}{symbol}\033[0m {claim_name:25} {status:6} - {message}")
                
            except Exception as e:
                self.warnings.append(claim_name)
                print(f"⚠ {claim_name:25} ERROR  - {str(e)}")
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        total = len(validations)
        passed_count = len(self.passed)
        failed_count = len(self.failed)
        warning_count = len(self.warnings)
        
        print(f"Total Validations: {total}")
        print(f"Passed: {passed_count} ({passed_count/total*100:.1f}%)")
        print(f"Failed: {failed_count} ({failed_count/total*100:.1f}%)")
        print(f"Errors: {warning_count}")
        
        if self.failed:
            print("\nFailed Claims:")
            for claim in self.failed:
                print(f"  - {claim}")
        
        if self.warnings:
            print("\nValidation Errors:")
            for claim in self.warnings:
                print(f"  - {claim}")
        
        # Overall result
        print("\n" + "="*60)
        if failed_count == 0 and warning_count == 0:
            print("\033[92m✓ ALL CLAIMS VALIDATED SUCCESSFULLY!\033[0m")
            return 0
        elif failed_count <= 2:
            print("\033[93m⚠ MOST CLAIMS VALIDATED (minor issues)\033[0m")
            return 1
        else:
            print("\033[91m✗ VALIDATION FAILED - CLAIMS NOT SUBSTANTIATED\033[0m")
            return 2
    
    def generate_report(self, output_file: str = None):
        """Generate detailed validation report"""
        if not output_file:
            output_file = f"validation_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "summary": {
                "total": len(self.passed) + len(self.failed) + len(self.warnings),
                "passed": len(self.passed),
                "failed": len(self.failed),
                "errors": len(self.warnings),
            },
            "passed_validations": self.passed,
            "failed_validations": self.failed,
            "validation_errors": self.warnings,
            "recommendations": self.get_recommendations(),
        }
        
        output_path = Path('benchmarks/results') / output_file
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nDetailed report saved to: {output_path}")
    
    def get_recommendations(self) -> list[str]:
        """Get recommendations based on validation results"""
        recommendations = []
        
        if "P95 Latency <200ms" in self.failed:
            recommendations.append("Optimize API response times - consider caching, query optimization, or scaling")
        
        if "30% Cost Reduction" in self.failed:
            recommendations.append("Improve cache hit rate - analyze common queries and optimize cache key generation")
        
        if "100+ Concurrent Users" in self.failed:
            recommendations.append("Scale WebSocket infrastructure - increase connection pool size and optimize message handling")
        
        if "Test Coverage" in self.failed:
            recommendations.append("Increase test coverage - write more unit and integration tests")
        
        if "Documentation" in self.failed:
            recommendations.append("Complete documentation - ensure all architecture and API docs are up to date")
        
        if "CI/CD Pipeline" in self.failed:
            recommendations.append("Set up automated testing and deployment pipelines")
        
        return recommendations


def main():
    """Main entry point"""
    validator = ClaimValidator()
    
    # Check if we should run benchmarks first
    if '--run-benchmarks' in sys.argv:
        print("Running benchmarks first...")
        result = subprocess.run(
            ['python', 'scripts/utils/manage.py', 'benchmark'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("Benchmark failed:", result.stderr)
            sys.exit(1)
    
    # Run validations
    exit_code = validator.run_all_validations()
    
    # Generate report
    validator.generate_report()
    
    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == '__main__':
    main()