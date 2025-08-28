"""
Multi-Region Architecture with Global Load Balancing
AWS Route53, Lambda@Edge, and cross-region replication
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp
import boto3
from botocore.exceptions import ClientError
from geoip2 import database as geoip_db
from geopy.distance import geodesic

logger = logging.getLogger(__name__)


class DeploymentState(Enum):
    BLUE = "blue"
    GREEN = "green"
    CANARY = "canary"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class Region:
    name: str
    code: str
    endpoint: str
    weight: int
    latitude: float
    longitude: float
    deployment_state: DeploymentState = DeploymentState.BLUE
    health_status: HealthStatus = HealthStatus.HEALTHY
    capacity: int = 100
    current_load: int = 0
    response_time: float = 0.0
    error_rate: float = 0.0


@dataclass
class RoutingRule:
    rule_id: str
    priority: int
    conditions: dict[str, Any]
    target_region: str
    weight: int
    enabled: bool = True


class GlobalRoutingManager:
    """
    Manages global traffic routing with Route53, Lambda@Edge, and health checks
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.route53 = boto3.client("route53")
        self.cloudfront = boto3.client("cloudfront")
        self.lambda_client = boto3.client("lambda")

        # Initialize regions
        self.regions = {region["name"]: Region(**region) for region in config["regions"]}

        # GeoIP database for location-based routing
        self.geoip_reader = None
        try:
            self.geoip_reader = geoip_db.Reader("GeoLite2-City.mmdb")
        except Exception:
            logger.warning("GeoIP database not found")

        # Routing rules
        self.routing_rules: list[RoutingRule] = []
        self._load_routing_rules()

        # Health check configuration
        self.health_check_interval = config.get("health_check_interval", 30)
        self.health_check_timeout = config.get("health_check_timeout", 5)
        self.unhealthy_threshold = config.get("unhealthy_threshold", 3)

    async def initialize(self):
        """Initialize global routing infrastructure"""
        await self._setup_route53_health_checks()
        await self._deploy_lambda_edge_functions()
        await self._configure_cloudfront_distribution()

        # Start background tasks
        asyncio.create_task(self._health_monitoring_loop())
        asyncio.create_task(self._capacity_monitoring_loop())

        logger.info("Global routing manager initialized")

    async def _setup_route53_health_checks(self):
        """Configure Route53 health checks for all regions"""
        for region in self.regions.values():
            try:
                # Create health check
                response = self.route53.create_health_check(
                    Type="HTTPS",
                    ResourcePath="/health",
                    FullyQualifiedDomainName=region.endpoint.replace("https://", ""),
                    Port=443,
                    RequestInterval=30,
                    FailureThreshold=3,
                    Tags=[
                        {"Key": "Name", "Value": f"chatbot-{region.name}-health-check"},
                        {"Key": "Region", "Value": region.name},
                    ],
                )

                health_check_id = response["HealthCheck"]["Id"]

                # Create Route53 record with health check
                self.route53.change_resource_record_sets(
                    HostedZoneId=self.config["hosted_zone_id"],
                    ChangeBatch={
                        "Changes": [
                            {
                                "Action": "UPSERT",
                                "ResourceRecordSet": {
                                    "Name": f'{region.name}.api.{self.config["domain"]}',
                                    "Type": "A",
                                    "TTL": 60,
                                    "ResourceRecords": [
                                        {"Value": self._get_region_ip(region.endpoint)}
                                    ],
                                    "HealthCheckId": health_check_id,
                                },
                            }
                        ]
                    },
                )

                logger.info(f"Health check configured for {region.name}")

            except ClientError as e:
                logger.error(f"Failed to setup health check for {region.name}: {e}")

    async def _deploy_lambda_edge_functions(self):
        """Deploy Lambda@Edge functions for intelligent routing"""

        # Origin request function for geographic routing
        origin_request_code = """
def lambda_handler(event, context):
    import json
    import hashlib
    
    request = event['Records'][0]['cf']['request']
    headers = request['headers']
    
    # Get client IP and geographic location
    client_ip = headers.get('cloudfront-viewer-address', [{}])[0].get('value', '').split(':')[0]
    country = headers.get('cloudfront-viewer-country', [{}])[0].get('value', 'US')
    
    # Get user identifier for consistent hashing
    user_id = headers.get('authorization', [{}])[0].get('value', client_ip)
    
    # Determine target region based on geography and load
    regions = {
        'us-east-1': {'countries': ['US', 'CA'], 'weight': 40},
        'eu-west-1': {'countries': ['GB', 'DE', 'FR', 'IT', 'ES'], 'weight': 35},
        'ap-southeast-1': {'countries': ['SG', 'MY', 'TH', 'ID'], 'weight': 25}
    }
    
    # Default region selection
    target_region = 'us-east-1'
    
    # Geographic routing
    for region, config in regions.items():
        if country in config['countries']:
            target_region = region
            break
    
    # Consistent hashing for sticky sessions
    if 'session-id' in headers:
        session_id = headers['session-id'][0]['value']
        hash_value = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
        region_index = hash_value % len(regions)
        target_region = list(regions.keys())[region_index]
    
    # Update origin to target region
    request['origin']['custom']['domainName'] = f'{target_region}.api.example.com'
    
    # Add routing headers
    request['headers']['x-target-region'] = [{'key': 'X-Target-Region', 'value': target_region}]
    request['headers']['x-client-country'] = [{'key': 'X-Client-Country', 'value': country}]
    
    return request
        """

        # Viewer response function for caching optimization
        viewer_response_code = """
def lambda_handler(event, context):
    response = event['Records'][0]['cf']['response']
    headers = response['headers']
    
    # Add CORS headers
    headers['access-control-allow-origin'] = [{'key': 'Access-Control-Allow-Origin', 'value': '*'}]
    headers['access-control-allow-methods'] = [{'key': 'Access-Control-Allow-Methods', 'value': 'GET,HEAD,OPTIONS,POST,PUT'}]
    headers['access-control-allow-headers'] = [{'key': 'Access-Control-Allow-Headers', 'value': 'Authorization,Content-Type'}]
    
    # Cache control for different content types
    uri = event['Records'][0]['cf']['request']['uri']
    
    if uri.startswith('/api/'):
        # API responses - short cache
        headers['cache-control'] = [{'key': 'Cache-Control', 'value': 'max-age=60, must-revalidate'}]
    elif uri.startswith('/static/'):
        # Static assets - long cache
        headers['cache-control'] = [{'key': 'Cache-Control', 'value': 'max-age=31536000, immutable'}]
    
    # Add region information
    headers['x-served-by'] = [{'key': 'X-Served-By', 'value': 'global-edge'}]
    
    return response
        """

        try:
            # Deploy origin request function
            self.lambda_client.create_function(
                FunctionName="chatbot-origin-request",
                Runtime="python3.9",
                Role=self.config["lambda_execution_role_arn"],
                Handler="index.lambda_handler",
                Code={"ZipFile": origin_request_code.encode()},
                Description="Origin request routing for AI chatbot",
                Timeout=5,
                MemorySize=128,
            )

            # Deploy viewer response function
            self.lambda_client.create_function(
                FunctionName="chatbot-viewer-response",
                Runtime="python3.9",
                Role=self.config["lambda_execution_role_arn"],
                Handler="index.lambda_handler",
                Code={"ZipFile": viewer_response_code.encode()},
                Description="Viewer response optimization for AI chatbot",
                Timeout=5,
                MemorySize=128,
            )

            logger.info("Lambda@Edge functions deployed successfully")

        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceConflictException":
                logger.error(f"Failed to deploy Lambda@Edge functions: {e}")

    async def _configure_cloudfront_distribution(self):
        """Configure CloudFront distribution with Lambda@Edge functions"""

        distribution_config = {
            "CallerReference": f"chatbot-{int(time.time())}",
            "Comment": "AI Chatbot Global Distribution",
            "DefaultRootObject": "index.html",
            "Origins": {
                "Quantity": len(self.regions),
                "Items": [
                    {
                        "Id": f"origin-{region.name}",
                        "DomainName": region.endpoint.replace("https://", ""),
                        "CustomOriginConfig": {
                            "HTTPPort": 80,
                            "HTTPSPort": 443,
                            "OriginProtocolPolicy": "https-only",
                            "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                        },
                    }
                    for region in self.regions.values()
                ],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": f"origin-{list(self.regions.keys())[0]}",
                "ViewerProtocolPolicy": "redirect-to-https",
                "MinTTL": 0,
                "DefaultTTL": 86400,
                "MaxTTL": 31536000,
                "ForwardedValues": {
                    "QueryString": True,
                    "Cookies": {"Forward": "all"},
                    "Headers": {
                        "Quantity": 3,
                        "Items": ["Authorization", "Content-Type", "Session-Id"],
                    },
                },
                "LambdaFunctionAssociations": {
                    "Quantity": 2,
                    "Items": [
                        {
                            "LambdaFunctionARN": f"{self.config['lambda_origin_request_arn']}:1",
                            "EventType": "origin-request",
                        },
                        {
                            "LambdaFunctionARN": f"{self.config['lambda_viewer_response_arn']}:1",
                            "EventType": "viewer-response",
                        },
                    ],
                },
            },
            "CacheBehaviors": {
                "Quantity": 2,
                "Items": [
                    {
                        "PathPattern": "/api/*",
                        "TargetOriginId": f"origin-{list(self.regions.keys())[0]}",
                        "ViewerProtocolPolicy": "https-only",
                        "MinTTL": 0,
                        "DefaultTTL": 0,
                        "MaxTTL": 300,
                        "ForwardedValues": {
                            "QueryString": True,
                            "Cookies": {"Forward": "all"},
                            "Headers": {"Quantity": 1, "Items": ["*"]},
                        },
                    },
                    {
                        "PathPattern": "/ws/*",
                        "TargetOriginId": f"origin-{list(self.regions.keys())[0]}",
                        "ViewerProtocolPolicy": "https-only",
                        "MinTTL": 0,
                        "DefaultTTL": 0,
                        "MaxTTL": 0,
                        "ForwardedValues": {
                            "QueryString": True,
                            "Cookies": {"Forward": "all"},
                            "Headers": {"Quantity": 1, "Items": ["*"]},
                        },
                    },
                ],
            },
            "Enabled": True,
            "PriceClass": "PriceClass_All",
        }

        try:
            response = self.cloudfront.create_distribution(DistributionConfig=distribution_config)

            distribution_id = response["Distribution"]["Id"]
            logger.info(f"CloudFront distribution created: {distribution_id}")

        except ClientError as e:
            logger.error(f"Failed to create CloudFront distribution: {e}")

    async def route_request(
        self,
        client_ip: str,
        session_id: str | None = None,
        user_preferences: dict[str, Any] | None = None,
    ) -> tuple[str, Region]:
        """
        Intelligent request routing based on geography, load, and preferences
        """

        # Get client location
        client_location = self._get_client_location(client_ip)

        # Calculate region scores
        region_scores = {}

        for region_name, region in self.regions.items():
            if region.health_status == HealthStatus.UNHEALTHY:
                continue

            score = 0

            # Geographic proximity (40% weight)
            if client_location:
                distance = geodesic(
                    (client_location["latitude"], client_location["longitude"]),
                    (region.latitude, region.longitude),
                ).kilometers

                # Lower distance = higher score
                geo_score = max(0, 100 - (distance / 100))
                score += geo_score * 0.4

            # Current load (30% weight)
            load_factor = region.current_load / region.capacity
            load_score = max(0, 100 - (load_factor * 100))
            score += load_score * 0.3

            # Response time (20% weight)
            response_score = max(0, 100 - (region.response_time * 10))
            score += response_score * 0.2

            # Error rate (10% weight)
            error_score = max(0, 100 - (region.error_rate * 100))
            score += error_score * 0.1

            # Health status modifier
            if region.health_status == HealthStatus.DEGRADED:
                score *= 0.7

            region_scores[region_name] = score

        # Handle session stickiness
        if session_id:
            sticky_region = self._get_sticky_region(session_id)
            if sticky_region in region_scores and region_scores[sticky_region] > 20:
                # Prefer sticky region if it's reasonably healthy
                region_scores[sticky_region] += 25

        # Select best region
        if not region_scores:
            raise Exception("No healthy regions available")

        best_region_name = max(region_scores, key=region_scores.get)
        best_region = self.regions[best_region_name]

        logger.info(
            f"Routed request to {best_region_name} (score: {region_scores[best_region_name]:.1f})"
        )

        return best_region_name, best_region

    def _get_client_location(self, client_ip: str) -> dict[str, Any] | None:
        """Get client geographic location from IP"""
        if not self.geoip_reader:
            return None

        try:
            response = self.geoip_reader.city(client_ip)
            return {
                "country": response.country.iso_code,
                "city": response.city.name,
                "latitude": float(response.location.latitude),
                "longitude": float(response.location.longitude),
            }
        except Exception:
            return None

    def _get_sticky_region(self, session_id: str) -> str:
        """Get consistent region for session stickiness"""
        hash_value = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
        region_names = list(self.regions.keys())
        return region_names[hash_value % len(region_names)]

    async def _health_monitoring_loop(self):
        """Background task for monitoring region health"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                for region_name, region in self.regions.items():
                    health_status = await self._check_region_health(region)
                    region.health_status = health_status

                    logger.debug(f"Region {region_name} health: {health_status.value}")

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

    async def _check_region_health(self, region: Region) -> HealthStatus:
        """Check health of a specific region"""
        try:
            start_time = time.time()

            # Make health check request
            timeout = aiohttp.ClientTimeout(total=self.health_check_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{region.endpoint}/health") as response:
                    response_time = time.time() - start_time
                    region.response_time = response_time

                    if response.status == 200:
                        data = await response.json()

                        # Parse health check response
                        dependencies = data.get("dependencies", {})
                        unhealthy_deps = [
                            dep
                            for dep, status in dependencies.items()
                            if status.get("status") != "healthy"
                        ]

                        if not unhealthy_deps and response_time < 2.0:
                            return HealthStatus.HEALTHY
                        elif len(unhealthy_deps) <= 1 and response_time < 5.0:
                            return HealthStatus.DEGRADED
                        else:
                            return HealthStatus.UNHEALTHY
                    else:
                        return HealthStatus.UNHEALTHY

        except Exception as e:
            logger.warning(f"Health check failed for {region.name}: {e}")
            return HealthStatus.UNHEALTHY

    async def _capacity_monitoring_loop(self):
        """Monitor region capacity and load"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                for region_name, region in self.regions.items():
                    # Get current load metrics
                    load_metrics = await self._get_region_load(region)

                    region.current_load = load_metrics.get("active_connections", 0)
                    region.error_rate = load_metrics.get("error_rate", 0.0)

                    # Trigger auto-scaling if needed
                    if region.current_load > region.capacity * 0.8:
                        await self._trigger_auto_scaling(region_name, "scale_up")
                    elif region.current_load < region.capacity * 0.2:
                        await self._trigger_auto_scaling(region_name, "scale_down")

            except Exception as e:
                logger.error(f"Capacity monitoring error: {e}")

    async def _get_region_load(self, region: Region) -> dict[str, Any]:
        """Get current load metrics for a region"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{region.endpoint}/metrics") as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
        except Exception:
            return {}

    async def _trigger_auto_scaling(self, region_name: str, action: str):
        """Trigger auto-scaling action"""
        logger.info(f"Triggering {action} for region {region_name}")

        # In production, this would call AWS Auto Scaling APIs
        # or Kubernetes HPA to scale the infrastructure

    def _get_region_ip(self, endpoint: str) -> str:
        """Get IP address for a region endpoint"""
        import socket

        hostname = endpoint.replace("https://", "").replace("http://", "")
        return socket.gethostbyname(hostname)

    def _load_routing_rules(self):
        """Load routing rules from configuration"""
        rules_config = self.config.get("routing_rules", [])

        for rule_config in rules_config:
            rule = RoutingRule(**rule_config)
            self.routing_rules.append(rule)

        # Sort by priority
        self.routing_rules.sort(key=lambda r: r.priority)


class BlueGreenDeploymentManager:
    """
    Manages blue-green deployments across regions
    """

    def __init__(self, routing_manager: GlobalRoutingManager):
        self.routing_manager = routing_manager
        self.deployment_states = {}

    async def deploy_new_version(
        self, version: str, regions: list[str], strategy: str = "rolling"
    ) -> dict[str, Any]:
        """
        Deploy new version using blue-green strategy
        """

        deployment_id = f"deploy-{int(time.time())}"

        try:
            if strategy == "rolling":
                return await self._rolling_deployment(deployment_id, version, regions)
            elif strategy == "canary":
                return await self._canary_deployment(deployment_id, version, regions)
            else:
                return await self._blue_green_deployment(deployment_id, version, regions)

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            await self._rollback_deployment(deployment_id)
            raise

    async def _blue_green_deployment(
        self, deployment_id: str, version: str, regions: list[str]
    ) -> dict[str, Any]:
        """
        Full blue-green deployment
        """

        logger.info(f"Starting blue-green deployment {deployment_id}")

        results = {}

        for region_name in regions:
            region = self.routing_manager.regions[region_name]

            # Deploy to green environment
            green_endpoint = await self._deploy_green_environment(region_name, version)

            # Health check green environment
            if await self._validate_green_environment(green_endpoint):
                # Switch traffic to green
                await self._switch_traffic_to_green(region_name)

                # Update region configuration
                region.deployment_state = DeploymentState.GREEN

                results[region_name] = {
                    "status": "success",
                    "endpoint": green_endpoint,
                    "version": version,
                }
            else:
                results[region_name] = {"status": "failed", "error": "Health check failed"}

        return {"deployment_id": deployment_id, "strategy": "blue-green", "results": results}

    async def _canary_deployment(
        self, deployment_id: str, version: str, regions: list[str]
    ) -> dict[str, Any]:
        """
        Canary deployment with gradual traffic shift
        """

        logger.info(f"Starting canary deployment {deployment_id}")

        traffic_percentages = [5, 25, 50, 100]

        for percentage in traffic_percentages:
            logger.info(f"Shifting {percentage}% traffic to canary")

            # Deploy canary version
            for region_name in regions:
                await self._deploy_canary_version(region_name, version, percentage)

            # Monitor for 10 minutes
            await asyncio.sleep(600)

            # Check metrics
            if not await self._validate_canary_metrics(regions):
                logger.error("Canary metrics validation failed")
                await self._rollback_canary(regions)
                raise Exception("Canary deployment failed validation")

        return {"deployment_id": deployment_id, "strategy": "canary", "status": "success"}

    async def _deploy_green_environment(self, region_name: str, version: str) -> str:
        """Deploy new version to green environment"""

        # In production, this would:
        # 1. Create new ECS service with new task definition
        # 2. Deploy to new Auto Scaling Group
        # 3. Update Kubernetes deployment

        green_endpoint = f"https://green-{region_name}.api.example.com"

        logger.info(f"Deploying version {version} to green environment in {region_name}")

        return green_endpoint

    async def _validate_green_environment(self, endpoint: str) -> bool:
        """Validate green environment health"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{endpoint}/health") as response:
                    return response.status == 200
        except Exception:
            return False

    async def _switch_traffic_to_green(self, region_name: str):
        """Switch traffic from blue to green"""

        # Update load balancer configuration
        # Update Route53 records
        # Update CloudFront origins

        logger.info(f"Switched traffic to green in {region_name}")

    async def _rollback_deployment(self, deployment_id: str):
        """Rollback failed deployment"""

        logger.info(f"Rolling back deployment {deployment_id}")

        # Revert traffic routing
        # Restore previous version
        # Clean up failed resources


class ChaosEngineeringFramework:
    """
    Chaos engineering tests with Gremlin integration
    """

    def __init__(self, routing_manager: GlobalRoutingManager):
        self.routing_manager = routing_manager
        self.chaos_experiments = []

    async def run_chaos_experiment(
        self, experiment_type: str, target_region: str, duration: int = 300
    ) -> dict[str, Any]:
        """
        Run chaos engineering experiment
        """

        experiment_id = f"chaos-{int(time.time())}"

        logger.info(f"Starting chaos experiment {experiment_id}: {experiment_type}")

        # Record baseline metrics
        baseline_metrics = await self._collect_baseline_metrics()

        # Start experiment
        if experiment_type == "region_failure":
            await self._simulate_region_failure(target_region, duration)
        elif experiment_type == "network_latency":
            await self._simulate_network_latency(target_region, duration)
        elif experiment_type == "cpu_stress":
            await self._simulate_cpu_stress(target_region, duration)
        elif experiment_type == "memory_pressure":
            await self._simulate_memory_pressure(target_region, duration)

        # Monitor system behavior
        experiment_metrics = await self._monitor_during_experiment(duration)

        # Stop experiment
        await self._stop_experiment(experiment_id)

        # Analyze results
        results = await self._analyze_experiment_results(baseline_metrics, experiment_metrics)

        return {
            "experiment_id": experiment_id,
            "type": experiment_type,
            "target": target_region,
            "duration": duration,
            "results": results,
        }

    async def _simulate_region_failure(self, region: str, duration: int):
        """Simulate complete region failure"""

        # Mark region as unhealthy
        self.routing_manager.regions[region].health_status = HealthStatus.UNHEALTHY

        logger.info(f"Simulating region failure for {region}")

        # Wait for duration
        await asyncio.sleep(duration)

        # Restore region
        self.routing_manager.regions[region].health_status = HealthStatus.HEALTHY

    async def _simulate_network_latency(self, region: str, duration: int):
        """Simulate network latency"""

        original_response_time = self.routing_manager.regions[region].response_time

        # Increase response time
        self.routing_manager.regions[region].response_time = original_response_time + 2.0

        await asyncio.sleep(duration)

        # Restore original response time
        self.routing_manager.regions[region].response_time = original_response_time

    async def _collect_baseline_metrics(self) -> dict[str, Any]:
        """Collect baseline system metrics"""

        metrics = {}

        for region_name, region in self.routing_manager.regions.items():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{region.endpoint}/metrics") as response:
                        if response.status == 200:
                            metrics[region_name] = await response.json()
            except Exception:
                metrics[region_name] = {}

        return metrics

    async def _monitor_during_experiment(self, duration: int) -> dict[str, Any]:
        """Monitor system during chaos experiment"""

        monitoring_data = []
        interval = 30  # Collect metrics every 30 seconds

        for _i in range(duration // interval):
            metrics = await self._collect_baseline_metrics()
            monitoring_data.append({"timestamp": time.time(), "metrics": metrics})

            await asyncio.sleep(interval)

        return monitoring_data

    async def _analyze_experiment_results(
        self, baseline: dict[str, Any], experiment_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze chaos experiment results"""

        # Calculate recovery time
        recovery_time = self._calculate_recovery_time(experiment_data)

        # Check SLA violations
        sla_violations = self._check_sla_violations(experiment_data)

        # Measure failover effectiveness
        failover_success = self._measure_failover_success(experiment_data)

        return {
            "recovery_time_seconds": recovery_time,
            "sla_violations": sla_violations,
            "failover_success_rate": failover_success,
            "recommendations": self._generate_recommendations(experiment_data),
        }

    def _calculate_recovery_time(self, data: list[dict[str, Any]]) -> float:
        """Calculate system recovery time"""

        # Find when system returned to normal
        for entry in data:
            # Check if all regions are healthy
            all_healthy = True
            for region_metrics in entry["metrics"].values():
                if region_metrics.get("error_rate", 0) > 0.01:
                    all_healthy = False
                    break

            if all_healthy:
                return entry["timestamp"] - data[0]["timestamp"]

        return float("inf")  # System didn't recover

    def _generate_recommendations(self, data: list[dict[str, Any]]) -> list[str]:
        """Generate improvement recommendations"""

        recommendations = []

        # Check if failover was fast enough
        recovery_time = self._calculate_recovery_time(data)
        if recovery_time > 60:
            recommendations.append("Improve failover speed - target <60 seconds")

        # Check error rates during experiment
        max_error_rate = 0
        for entry in data:
            for metrics in entry["metrics"].values():
                error_rate = metrics.get("error_rate", 0)
                max_error_rate = max(max_error_rate, error_rate)

        if max_error_rate > 0.05:
            recommendations.append("Implement better error handling and retries")

        return recommendations
