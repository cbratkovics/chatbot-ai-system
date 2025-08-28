"""
Custom Prometheus Exporters for AI Chatbot System
Enterprise-grade metrics collection for business and technical KPIs
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import anthropic
import asyncpg
import boto3
import numpy as np
import openai
import redis.asyncio as redis
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from prometheus_client.core import CollectorRegistry

logger = logging.getLogger(__name__)

class MetricCategory(Enum):
    BUSINESS = "business"
    TECHNICAL = "technical"
    COST = "cost"
    AI_MODEL = "ai_model"
    SECURITY = "security"

@dataclass
class CustomMetric:
    name: str
    description: str
    category: MetricCategory
    metric_type: str  # "gauge", "counter", "histogram", "summary"
    labels: list[str]
    value: float
    timestamp: datetime

class AIModelMetricsExporter:
    """
    Custom exporter for AI model performance and usage metrics
    """
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.registry = CollectorRegistry()
        
        # Database connections
        self.db_pool = None
        self.redis = redis.from_url(config['redis_url'])
        
        # AI API clients
        self.openai_client = openai.AsyncOpenAI(api_key=config.get('openai_api_key'))
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=config.get('anthropic_api_key'))
        
        # Prometheus metrics
        self._setup_metrics()
        
    def _setup_metrics(self):
        """Setup Prometheus metrics"""
        
        # Model Performance Metrics
        self.model_response_time = Histogram(
            'ai_model_response_time_seconds',
            'Response time for AI model requests',
            ['model', 'provider', 'region'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.model_tokens_used = Counter(
            'ai_model_tokens_total',
            'Total tokens used by AI models',
            ['model', 'provider', 'token_type'],  # token_type: input, output
            registry=self.registry
        )
        
        self.model_requests_total = Counter(
            'ai_model_requests_total',
            'Total requests to AI models',
            ['model', 'provider', 'status'],  # status: success, error, timeout
            registry=self.registry
        )
        
        self.model_cost_usd = Counter(
            'ai_model_cost_usd_total',
            'Total cost in USD for AI model usage',
            ['model', 'provider', 'cost_type'],  # cost_type: input, output
            registry=self.registry
        )
        
        self.model_quality_score = Gauge(
            'ai_model_quality_score',
            'Quality score for AI model responses (0-1)',
            ['model', 'provider', 'metric'],  # metric: coherence, relevance, safety
            registry=self.registry
        )
        
        self.model_availability = Gauge(
            'ai_model_availability',
            'Availability status of AI models (1=available, 0=unavailable)',
            ['model', 'provider'],
            registry=self.registry
        )
        
        # Cache Performance
        self.cache_hit_rate = Gauge(
            'ai_cache_hit_rate',
            'Cache hit rate for AI responses',
            ['cache_type'],  # cache_type: semantic, exact
            registry=self.registry
        )
        
        self.cache_size_bytes = Gauge(
            'ai_cache_size_bytes',
            'Size of AI response cache in bytes',
            ['cache_type'],
            registry=self.registry
        )
        
        # Model Load Distribution
        self.model_load_distribution = Gauge(
            'ai_model_load_percentage',
            'Percentage of requests going to each model',
            ['model', 'provider'],
            registry=self.registry
        )
        
        # Rate Limiting
        self.rate_limit_remaining = Gauge(
            'ai_model_rate_limit_remaining',
            'Remaining rate limit for AI model APIs',
            ['model', 'provider', 'limit_type'],  # limit_type: requests, tokens
            registry=self.registry
        )
        
    async def initialize(self):
        """Initialize the exporter"""
        self.db_pool = await asyncpg.create_pool(self.config['database_url'])
        
        # Start metrics collection
        asyncio.create_task(self._collect_metrics_loop())
        
        logger.info("AI Model Metrics Exporter initialized")
        
    async def _collect_metrics_loop(self):
        """Main metrics collection loop"""
        while True:
            try:
                await self._collect_model_metrics()
                await self._collect_cache_metrics()
                await self._collect_availability_metrics()
                await asyncio.sleep(30)  # Collect every 30 seconds
                
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(60)
                
    async def _collect_model_metrics(self):
        """Collect AI model performance metrics"""
        try:
            # Query recent model usage from database
            async with self.db_pool.acquire() as conn:
                # Get model usage stats from last 5 minutes
                query = """
                    SELECT 
                        model,
                        provider,
                        COUNT(*) as request_count,
                        AVG(response_time) as avg_response_time,
                        SUM(input_tokens) as total_input_tokens,
                        SUM(output_tokens) as total_output_tokens,
                        SUM(cost) as total_cost,
                        AVG(quality_score) as avg_quality_score,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                        COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count
                    FROM ai_model_requests 
                    WHERE created_at > NOW() - INTERVAL '5 minutes'
                    GROUP BY model, provider
                """
                
                results = await conn.fetch(query)
                
                for row in results:
                    model = row['model']
                    provider = row['provider']
                    
                    # Update metrics
                    self.model_requests_total.labels(
                        model=model, provider=provider, status='success'
                    ).inc(row['success_count'])
                    
                    self.model_requests_total.labels(
                        model=model, provider=provider, status='error'
                    ).inc(row['error_count'])
                    
                    self.model_tokens_used.labels(
                        model=model, provider=provider, token_type='input'
                    ).inc(row['total_input_tokens'] or 0)
                    
                    self.model_tokens_used.labels(
                        model=model, provider=provider, token_type='output'
                    ).inc(row['total_output_tokens'] or 0)
                    
                    self.model_cost_usd.labels(
                        model=model, provider=provider, cost_type='total'
                    ).inc(row['total_cost'] or 0)
                    
                    if row['avg_quality_score']:
                        self.model_quality_score.labels(
                            model=model, provider=provider, metric='overall'
                        ).set(row['avg_quality_score'])
                    
                    # Update response time histogram (simulated from average)
                    if row['avg_response_time']:
                        for _ in range(int(row['request_count'])):
                            self.model_response_time.labels(
                                model=model, provider=provider, region='us-east-1'
                            ).observe(row['avg_response_time'])
                            
        except Exception as e:
            logger.error(f"Model metrics collection error: {e}")
            
    async def _collect_cache_metrics(self):
        """Collect cache performance metrics"""
        try:
            # Get cache statistics from Redis
            cache_info = await self.redis.info('memory')
            
            # Semantic cache hit rate
            semantic_hits = await self.redis.get('cache:semantic:hits') or 0
            semantic_misses = await self.redis.get('cache:semantic:misses') or 0
            
            if int(semantic_hits) + int(semantic_misses) > 0:
                hit_rate = int(semantic_hits) / (int(semantic_hits) + int(semantic_misses))
                self.cache_hit_rate.labels(cache_type='semantic').set(hit_rate)
                
            # Cache size
            self.cache_size_bytes.labels(cache_type='semantic').set(
                cache_info.get('used_memory', 0)
            )
            
        except Exception as e:
            logger.error(f"Cache metrics collection error: {e}")
            
    async def _collect_availability_metrics(self):
        """Collect AI model availability metrics"""
        try:
            models_to_check = [
                ('gpt-4', 'openai'),
                ('gpt-3.5-turbo', 'openai'),
                ('claude-3-opus', 'anthropic'),
                ('claude-3-sonnet', 'anthropic')
            ]
            
            for model, provider in models_to_check:
                try:
                    # Make a lightweight test request
                    if provider == 'openai':
                        response = await self.openai_client.models.retrieve(model)
                        available = 1 if response else 0
                    elif provider == 'anthropic':
                        # Anthropic doesn't have a models endpoint, use a small completion
                        response = await self.anthropic_client.messages.create(
                            model=model,
                            max_tokens=1,
                            messages=[{"role": "user", "content": "Hi"}]
                        )
                        available = 1 if response else 0
                    else:
                        available = 0
                        
                    self.model_availability.labels(model=model, provider=provider).set(available)
                    
                except Exception:
                    self.model_availability.labels(model=model, provider=provider).set(0)
                    
        except Exception as e:
            logger.error(f"Availability metrics collection error: {e}")

class BusinessMetricsExporter:
    """
    Custom exporter for business KPIs and user engagement metrics
    """
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.registry = CollectorRegistry()
        self.db_pool = None
        self.redis = redis.from_url(config['redis_url'])
        
        self._setup_metrics()
        
    def _setup_metrics(self):
        """Setup business metrics"""
        
        # User Engagement
        self.active_users = Gauge(
            'chatbot_active_users',
            'Number of active users',
            ['time_window'],  # 1h, 24h, 7d, 30d
            registry=self.registry
        )
        
        self.new_user_registrations = Counter(
            'chatbot_user_registrations_total',
            'Total user registrations',
            ['source'],  # organic, referral, paid
            registry=self.registry
        )
        
        self.user_retention_rate = Gauge(
            'chatbot_user_retention_rate',
            'User retention rate',
            ['cohort_period'],  # weekly, monthly
            registry=self.registry
        )
        
        # Conversation Metrics
        self.conversations_started = Counter(
            'chatbot_conversations_started_total',
            'Total conversations started',
            ['user_type'],  # free, premium, enterprise
            registry=self.registry
        )
        
        self.conversation_length = Histogram(
            'chatbot_conversation_length_messages',
            'Number of messages per conversation',
            ['user_type'],
            buckets=[1, 3, 5, 10, 20, 50, 100],
            registry=self.registry
        )
        
        self.conversation_duration = Histogram(
            'chatbot_conversation_duration_seconds',
            'Duration of conversations',
            ['user_type'],
            buckets=[60, 300, 900, 1800, 3600, 7200],
            registry=self.registry
        )
        
        # Revenue Metrics
        self.monthly_recurring_revenue = Gauge(
            'chatbot_mrr_usd',
            'Monthly Recurring Revenue in USD',
            ['plan_type'],
            registry=self.registry
        )
        
        self.customer_lifetime_value = Gauge(
            'chatbot_customer_ltv_usd',
            'Customer Lifetime Value in USD',
            ['plan_type'],
            registry=self.registry
        )
        
        self.churn_rate = Gauge(
            'chatbot_churn_rate',
            'Customer churn rate',
            ['plan_type'],
            registry=self.registry
        )
        
        # Feature Usage
        self.feature_usage = Counter(
            'chatbot_feature_usage_total',
            'Feature usage counts',
            ['feature', 'user_type'],
            registry=self.registry
        )
        
        self.api_usage = Counter(
            'chatbot_api_calls_total',
            'API calls by external developers',
            ['api_version', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        # Customer Satisfaction
        self.satisfaction_score = Gauge(
            'chatbot_satisfaction_score',
            'Customer satisfaction score (1-5)',
            ['feedback_type'],  # response_quality, overall_experience
            registry=self.registry
        )
        
        self.net_promoter_score = Gauge(
            'chatbot_net_promoter_score',
            'Net Promoter Score (-100 to 100)',
            [],
            registry=self.registry
        )
        
    async def initialize(self):
        """Initialize the exporter"""
        self.db_pool = await asyncpg.create_pool(self.config['database_url'])
        
        # Start metrics collection
        asyncio.create_task(self._collect_business_metrics_loop())
        
        logger.info("Business Metrics Exporter initialized")
        
    async def _collect_business_metrics_loop(self):
        """Main business metrics collection loop"""
        while True:
            try:
                await self._collect_user_metrics()
                await self._collect_conversation_metrics()
                await self._collect_revenue_metrics()
                await self._collect_satisfaction_metrics()
                await asyncio.sleep(300)  # Collect every 5 minutes
                
            except Exception as e:
                logger.error(f"Business metrics collection error: {e}")
                await asyncio.sleep(300)
                
    async def _collect_user_metrics(self):
        """Collect user engagement metrics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Active users in different time windows
                time_windows = {
                    '1h': 'NOW() - INTERVAL \'1 hour\'',
                    '24h': 'NOW() - INTERVAL \'24 hours\'',
                    '7d': 'NOW() - INTERVAL \'7 days\'',
                    '30d': 'NOW() - INTERVAL \'30 days\''
                }
                
                for window, sql_interval in time_windows.items():
                    query = f"""
                        SELECT COUNT(DISTINCT user_id) as active_users
                        FROM user_sessions
                        WHERE last_activity > {sql_interval}
                        AND is_active = true
                    """
                    
                    result = await conn.fetchrow(query)
                    self.active_users.labels(time_window=window).set(
                        result['active_users'] or 0
                    )
                    
                # New registrations in last hour
                new_users_query = """
                    SELECT COUNT(*) as new_users
                    FROM users
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """
                
                result = await conn.fetchrow(new_users_query)
                self.new_user_registrations.labels(source='organic').inc(
                    result['new_users'] or 0
                )
                
        except Exception as e:
            logger.error(f"User metrics collection error: {e}")
            
    async def _collect_conversation_metrics(self):
        """Collect conversation metrics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Conversations started in last hour
                query = """
                    SELECT 
                        u.plan_type,
                        COUNT(*) as conversations_started,
                        AVG(s.message_count) as avg_messages,
                        AVG(EXTRACT(EPOCH FROM (s.updated_at - s.created_at))) as avg_duration
                    FROM chat_sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY u.plan_type
                """
                
                results = await conn.fetch(query)
                
                for row in results:
                    plan_type = row['plan_type'] or 'free'
                    
                    self.conversations_started.labels(user_type=plan_type).inc(
                        row['conversations_started'] or 0
                    )
                    
                    if row['avg_messages']:
                        for _ in range(int(row['conversations_started'])):
                            self.conversation_length.labels(user_type=plan_type).observe(
                                row['avg_messages']
                            )
                            
                    if row['avg_duration']:
                        for _ in range(int(row['conversations_started'])):
                            self.conversation_duration.labels(user_type=plan_type).observe(
                                row['avg_duration']
                            )
                            
        except Exception as e:
            logger.error(f"Conversation metrics collection error: {e}")
            
    async def _collect_revenue_metrics(self):
        """Collect revenue and business metrics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Monthly Recurring Revenue
                mrr_query = """
                    SELECT 
                        plan_type,
                        SUM(monthly_amount) as mrr
                    FROM subscriptions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.status = 'active'
                    GROUP BY plan_type
                """
                
                results = await conn.fetch(mrr_query)
                
                for row in results:
                    self.monthly_recurring_revenue.labels(
                        plan_type=row['plan_type']
                    ).set(row['mrr'] or 0)
                    
                # Churn rate (monthly)
                churn_query = """
                    SELECT 
                        plan_type,
                        COUNT(CASE WHEN cancelled_at > NOW() - INTERVAL '30 days' THEN 1 END)::float /
                        NULLIF(COUNT(*), 0) as churn_rate
                    FROM subscriptions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.created_at < NOW() - INTERVAL '30 days'
                    GROUP BY plan_type
                """
                
                results = await conn.fetch(churn_query)
                
                for row in results:
                    self.churn_rate.labels(
                        plan_type=row['plan_type']
                    ).set(row['churn_rate'] or 0)
                    
        except Exception as e:
            logger.error(f"Revenue metrics collection error: {e}")
            
    async def _collect_satisfaction_metrics(self):
        """Collect customer satisfaction metrics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Average satisfaction scores
                satisfaction_query = """
                    SELECT 
                        feedback_type,
                        AVG(rating) as avg_rating
                    FROM user_feedback
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY feedback_type
                """
                
                results = await conn.fetch(satisfaction_query)
                
                for row in results:
                    self.satisfaction_score.labels(
                        feedback_type=row['feedback_type']
                    ).set(row['avg_rating'] or 0)
                    
                # Net Promoter Score
                nps_query = """
                    SELECT 
                        COUNT(CASE WHEN rating >= 9 THEN 1 END)::float /
                        NULLIF(COUNT(*), 0) * 100 -
                        COUNT(CASE WHEN rating <= 6 THEN 1 END)::float /
                        NULLIF(COUNT(*), 0) * 100 as nps
                    FROM user_feedback
                    WHERE feedback_type = 'nps'
                    AND created_at > NOW() - INTERVAL '30 days'
                """
                
                result = await conn.fetchrow(nps_query)
                if result and result['nps'] is not None:
                    self.net_promoter_score.set(result['nps'])
                    
        except Exception as e:
            logger.error(f"Satisfaction metrics collection error: {e}")

class CostMonitoringExporter:
    """
    Custom exporter for cost monitoring and FinOps metrics
    """
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.registry = CollectorRegistry()
        
        # AWS clients
        self.cloudwatch = boto3.client('cloudwatch', region_name=config.get('aws_region', 'us-east-1'))
        self.cost_explorer = boto3.client('ce', region_name='us-east-1')  # Cost Explorer is only in us-east-1
        
        self._setup_metrics()
        
    def _setup_metrics(self):
        """Setup cost monitoring metrics"""
        
        # Infrastructure Costs
        self.infrastructure_cost_daily = Gauge(
            'infrastructure_cost_usd_daily',
            'Daily infrastructure cost in USD',
            ['service', 'region', 'environment'],
            registry=self.registry
        )
        
        self.infrastructure_cost_monthly = Gauge(
            'infrastructure_cost_usd_monthly',
            'Monthly infrastructure cost in USD',
            ['service', 'region', 'environment'],
            registry=self.registry
        )
        
        # AI API Costs
        self.ai_api_cost_hourly = Counter(
            'ai_api_cost_usd_hourly',
            'Hourly AI API cost in USD',
            ['provider', 'model', 'cost_type'],
            registry=self.registry
        )
        
        self.cost_per_request = Histogram(
            'cost_per_request_usd',
            'Cost per request in USD',
            ['service', 'model'],
            buckets=[0.001, 0.01, 0.1, 1.0, 10.0],
            registry=self.registry
        )
        
        # Resource Utilization
        self.resource_utilization = Gauge(
            'resource_utilization_percentage',
            'Resource utilization percentage',
            ['resource_type', 'resource_id'],
            registry=self.registry
        )
        
        # Cost Optimization Metrics
        self.cost_optimization_savings = Counter(
            'cost_optimization_savings_usd',
            'Cost savings from optimization in USD',
            ['optimization_type'],
            registry=self.registry
        )
        
        self.rightsizing_recommendations = Gauge(
            'rightsizing_recommendations_count',
            'Number of rightsizing recommendations',
            ['resource_type', 'recommendation_type'],
            registry=self.registry
        )
        
        # Budget and Alerts
        self.budget_utilization = Gauge(
            'budget_utilization_percentage',
            'Budget utilization percentage',
            ['budget_name', 'period'],
            registry=self.registry
        )
        
        self.cost_anomalies = Counter(
            'cost_anomalies_detected_total',
            'Number of cost anomalies detected',
            ['service', 'anomaly_type'],
            registry=self.registry
        )
        
    async def initialize(self):
        """Initialize the cost monitoring exporter"""
        
        # Start metrics collection
        asyncio.create_task(self._collect_cost_metrics_loop())
        
        logger.info("Cost Monitoring Exporter initialized")
        
    async def _collect_cost_metrics_loop(self):
        """Main cost metrics collection loop"""
        while True:
            try:
                await self._collect_aws_costs()
                await self._collect_ai_api_costs()
                await self._collect_utilization_metrics()
                await asyncio.sleep(3600)  # Collect every hour
                
            except Exception as e:
                logger.error(f"Cost metrics collection error: {e}")
                await asyncio.sleep(1800)  # Retry in 30 minutes on error
                
    async def _collect_aws_costs(self):
        """Collect AWS infrastructure costs"""
        try:
            # Get daily costs for last 7 days
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={
                    'Start': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                    'End': datetime.now().strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )
            
            for result in response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    region = group['Keys'][1]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    
                    self.infrastructure_cost_daily.labels(
                        service=service,
                        region=region,
                        environment='production'
                    ).set(cost)
                    
        except Exception as e:
            logger.error(f"AWS cost collection error: {e}")
            
    async def _collect_ai_api_costs(self):
        """Collect AI API costs from usage data"""
        try:
            # This would typically read from a cost tracking database
            # For demonstration, we'll use sample data
            
            ai_providers = {
                'openai': {
                    'gpt-4': {'input': 0.03, 'output': 0.06},
                    'gpt-3.5-turbo': {'input': 0.001, 'output': 0.002}
                },
                'anthropic': {
                    'claude-3-opus': {'input': 0.015, 'output': 0.075},
                    'claude-3-sonnet': {'input': 0.003, 'output': 0.015}
                }
            }
            
            # Sample usage data (would come from actual usage tracking)
            for provider, models in ai_providers.items():
                for model, costs in models.items():
                    # Simulate hourly usage
                    input_tokens = np.random.randint(10000, 100000)
                    output_tokens = np.random.randint(5000, 50000)
                    
                    input_cost = (input_tokens / 1000) * costs['input']
                    output_cost = (output_tokens / 1000) * costs['output']
                    
                    self.ai_api_cost_hourly.labels(
                        provider=provider,
                        model=model,
                        cost_type='input'
                    ).inc(input_cost)
                    
                    self.ai_api_cost_hourly.labels(
                        provider=provider,
                        model=model,
                        cost_type='output'
                    ).inc(output_cost)
                    
        except Exception as e:
            logger.error(f"AI API cost collection error: {e}")
            
    async def _collect_utilization_metrics(self):
        """Collect resource utilization metrics"""
        try:
            # Get CloudWatch metrics for resource utilization
            metrics_to_collect = [
                ('AWS/EC2', 'CPUUtilization', 'InstanceId'),
                ('AWS/RDS', 'CPUUtilization', 'DBInstanceIdentifier'),
                ('AWS/ElastiCache', 'CPUUtilization', 'CacheClusterId')
            ]
            
            for namespace, metric_name, _dimension_name in metrics_to_collect:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=[],
                    StartTime=datetime.utcnow() - timedelta(hours=1),
                    EndTime=datetime.utcnow(),
                    Period=3600,
                    Statistics=['Average']
                )
                
                for datapoint in response['Datapoints']:
                    utilization = datapoint['Average']
                    
                    self.resource_utilization.labels(
                        resource_type=namespace.split('/')[-1].lower(),
                        resource_id='aggregate'
                    ).set(utilization)
                    
        except Exception as e:
            logger.error(f"Utilization metrics collection error: {e}")

class ObservabilityManager:
    """
    Main manager for all custom exporters and observability components
    """
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.exporters = {}
        
    async def initialize(self):
        """Initialize all exporters"""
        
        # Initialize AI Model Metrics Exporter
        if self.config.get('enable_ai_metrics', True):
            self.exporters['ai_model'] = AIModelMetricsExporter(self.config)
            await self.exporters['ai_model'].initialize()
            
            # Start HTTP server for AI model metrics
            start_http_server(8081, registry=self.exporters['ai_model'].registry)
            
        # Initialize Business Metrics Exporter
        if self.config.get('enable_business_metrics', True):
            self.exporters['business'] = BusinessMetricsExporter(self.config)
            await self.exporters['business'].initialize()
            
            # Start HTTP server for business metrics
            start_http_server(8082, registry=self.exporters['business'].registry)
            
        # Initialize Cost Monitoring Exporter
        if self.config.get('enable_cost_metrics', True):
            self.exporters['cost'] = CostMonitoringExporter(self.config)
            await self.exporters['cost'].initialize()
            
            # Start HTTP server for cost metrics
            start_http_server(8083, registry=self.exporters['cost'].registry)
            
        logger.info("All observability exporters initialized")
        
    async def shutdown(self):
        """Shutdown all exporters"""
        for exporter in self.exporters.values():
            if hasattr(exporter, 'shutdown'):
                await exporter.shutdown()
                
        logger.info("Observability exporters shut down")

# Example usage
async def main():
    config = {
        'database_url': 'postgresql://user:pass@localhost/chatbot',
        'redis_url': 'redis://localhost:6379',
        'openai_api_key': 'sk-...',
        'anthropic_api_key': 'sk-ant-...',
        'aws_region': 'us-east-1',
        'enable_ai_metrics': True,
        'enable_business_metrics': True,
        'enable_cost_metrics': True
    }
    
    manager = ObservabilityManager(config)
    await manager.initialize()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())