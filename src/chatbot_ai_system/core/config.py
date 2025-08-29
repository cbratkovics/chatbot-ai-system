"""Application configuration management."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Application
    APP_NAME: str = Field(default="Enterprise Chatbot Platform")
    VERSION: str = Field(default="1.0.0")
    APP_VERSION: str = Field(default="1.0.0")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    APP_DEBUG: bool = Field(default=False)
    PORT: int = Field(default=8000)
    APP_PORT: int = Field(default=8000)
    APP_HOST: str = Field(default="0.0.0.0")
    WORKERS: int = Field(default=4)
    APP_WORKERS: int = Field(default=4)
    APP_RELOAD: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # Security - Core required fields
    SECRET_KEY: str = Field(default="default-secret-key-change-in-production")
    JWT_SECRET_KEY: str = Field(default="default-jwt-secret-key")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_MINUTES: int = Field(default=30)
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    JWT_ISSUER: str = Field(default="ai-chatbot-system")
    JWT_AUDIENCE: str = Field(default="ai-chatbot-api")
    ALLOWED_ORIGINS: list[str] = Field(default=["*"])

    # CORS Configuration
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8080")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True)
    CORS_ALLOW_METHODS: str = Field(default="GET,POST,PUT,DELETE,OPTIONS")
    CORS_ALLOW_HEADERS: str = Field(default="*")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://chatbot_user:secure_password@localhost:5432/chatbot_db"
    )
    DATABASE_URL_TEST: str = Field(default="")
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=40)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)
    DATABASE_ECHO: bool = Field(default=False)
    DATABASE_SSL_MODE: str = Field(default="prefer")
    TEST_DATABASE_URL: str = Field(default="")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: str | None = Field(default=None)
    REDIS_MAX_CONNECTIONS: int = Field(default=100)
    REDIS_SOCKET_TIMEOUT: int = Field(default=5)
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(default=5)
    REDIS_DECODE_RESPONSES: bool = Field(default=True)
    CACHE_TTL: int = Field(default=3600)
    TEST_REDIS_URL: str = Field(default="redis://localhost:6379/1")

    # AI Providers
    PROVIDER_A_API_KEY: str = Field(default="")
    PROVIDER_A_BASE_URL: str = Field(default="")
    PROVIDER_B_API_KEY: str = Field(default="")
    PROVIDER_B_BASE_URL: str = Field(default="")

    # OpenAI
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_API_BASE: str = Field(default="https://api.openai.com/v1")
    OPENAI_API_VERSION: str = Field(default="2024-02-01")
    OPENAI_DEFAULT_MODEL: str = Field(default="gpt-4-turbo-preview")
    OPENAI_TIMEOUT_SECONDS: int = Field(default=30)
    OPENAI_MAX_RETRIES: int = Field(default=3)

    # Anthropic
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_API_BASE: str = Field(default="https://api.anthropic.com")
    ANTHROPIC_API_VERSION: str = Field(default="2024-01-01")
    ANTHROPIC_DEFAULT_MODEL: str = Field(default="claude-3-opus-20240229")
    ANTHROPIC_TIMEOUT_SECONDS: int = Field(default=30)
    ANTHROPIC_MAX_RETRIES: int = Field(default=3)

    # Llama
    LLAMA_API_ENDPOINT: str = Field(default="http://localhost:11434")
    LLAMA_API_KEY: str = Field(default="")
    LLAMA_DEFAULT_MODEL: str = Field(default="llama-3-70b")
    LLAMA_TIMEOUT_SECONDS: int = Field(default=60)
    LLAMA_MAX_RETRIES: int = Field(default=2)

    # Model Router
    DEFAULT_MODEL_PROVIDER: str = Field(default="openai")
    MODEL_FALLBACK_ENABLED: bool = Field(default=True)
    MODEL_FALLBACK_ORDER: str = Field(default="openai,anthropic,llama")
    MODEL_SELECTION_STRATEGY: str = Field(default="latency_optimized")

    # Vector Database
    VECTOR_DB_PROVIDER: str = Field(default="pinecone")
    VECTOR_DB_URL: str = Field(default="")
    VECTOR_DB_API_KEY: str = Field(default="")
    VECTOR_DB_INDEX_NAME: str = Field(default="ai-chatbot-system")
    VECTOR_DB_DIMENSION: int = Field(default=1024)
    VECTOR_DB_METRIC: str = Field(default="cosine")

    # Monitoring
    JAEGER_ENABLED: bool = Field(default=False)
    JAEGER_AGENT_HOST: str = Field(default="localhost")
    JAEGER_AGENT_PORT: int = Field(default=6831)
    JAEGER_SERVICE_NAME: str = Field(default="ai-chatbot-api")
    JAEGER_SAMPLER_TYPE: str = Field(default="probabilistic")
    JAEGER_SAMPLER_PARAM: float = Field(default=0.1)

    PROMETHEUS_ENABLED: bool = Field(default=False)
    PROMETHEUS_PORT: int = Field(default=9090)
    METRICS_PATH: str = Field(default="/metrics")

    GRAFANA_ENABLED: bool = Field(default=False)
    GRAFANA_PORT: int = Field(default=3000)
    GRAFANA_ADMIN_PASSWORD: str = Field(default="admin")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_PERIOD: int = Field(default=60)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=100)
    RATE_LIMIT_REQUESTS_PER_HOUR: int = Field(default=5000)
    RATE_LIMIT_TOKENS_PER_MINUTE: int = Field(default=10000)
    RATE_LIMIT_TOKENS_PER_HOUR: int = Field(default=500000)
    RATE_LIMIT_BURST_SIZE: int = Field(default=20)

    # Multi-tenancy
    TENANT_ISOLATION_MODE: str = Field(default="strict")
    DEFAULT_TENANT_ID: str = Field(default="default")
    TENANT_HEADER: str = Field(default="X-Tenant-ID")
    REQUIRE_TENANT_ID: bool = Field(default=True)

    # Usage Quotas
    QUOTA_ENABLED: bool = Field(default=True)
    QUOTA_MONTHLY_REQUESTS: int = Field(default=100000)
    QUOTA_MONTHLY_TOKENS: int = Field(default=10000000)
    QUOTA_MAX_CONVERSATION_LENGTH: int = Field(default=100)
    QUOTA_MAX_MESSAGE_LENGTH: int = Field(default=4000)

    # Caching
    ENABLE_SEMANTIC_CACHE: bool = Field(default=True)
    SEMANTIC_CACHE_TTL_SECONDS: int = Field(default=3600)
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = Field(default=0.95)
    SEMANTIC_CACHE_MAX_ENTRIES: int = Field(default=10000)
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = Field(default="text-embedding-ada-002")
    RESPONSE_CACHE_TTL_SECONDS: int = Field(default=300)
    RESPONSE_CACHE_MAX_SIZE_MB: int = Field(default=100)

    # WebSocket
    WS_ENABLED: bool = Field(default=True)
    WS_PATH: str = Field(default="/ws")
    WS_HEARTBEAT_INTERVAL: int = Field(default=30)
    WS_MAX_CONNECTIONS: int = Field(default=1000)
    WS_MAX_CONNECTIONS_PER_USER: int = Field(default=5)
    WS_MESSAGE_QUEUE_SIZE: int = Field(default=1000)
    WS_RECONNECT_TIMEOUT: int = Field(default=60)
    WS_PING_INTERVAL: int = Field(default=25)
    WS_PONG_TIMEOUT: int = Field(default=10)

    # API Configuration
    API_VERSION: str = Field(default="v1")
    API_PREFIX: str = Field(default="/api")
    API_DOCS_ENABLED: bool = Field(default=True)
    API_DOCS_PATH: str = Field(default="/docs")
    API_REDOC_PATH: str = Field(default="/redoc")
    API_KEY_HEADER: str = Field(default="X-API-Key")
    REQUIRE_API_KEY: bool = Field(default=False)
    MASTER_API_KEY: str = Field(default="")

    # Session
    SESSION_SECRET_KEY: str = Field(default="your-session-secret-key")
    SESSION_COOKIE_NAME: str = Field(default="chatbot_session")
    SESSION_COOKIE_SECURE: bool = Field(default=False)
    SESSION_COOKIE_HTTPONLY: bool = Field(default=True)
    SESSION_COOKIE_SAMESITE: str = Field(default="lax")

    # Performance
    CONNECTION_POOL_SIZE: int = Field(default=100)
    MAX_CONNECTIONS_PER_USER: int = Field(default=5)
    CONNECTION_TIMEOUT_SECONDS: int = Field(default=30)
    REQUEST_TIMEOUT_SECONDS: int = Field(default=30)
    MAX_REQUEST_SIZE_MB: int = Field(default=10)
    STREAMING_CHUNK_SIZE: int = Field(default=1024)
    STREAMING_TIMEOUT_SECONDS: int = Field(default=120)

    # Circuit Breaker
    CIRCUIT_BREAKER_ENABLED: bool = Field(default=True)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=5)
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = Field(default=60)
    CIRCUIT_BREAKER_EXPECTED_EXCEPTION: str = Field(default="TimeoutError")

    # Retry Policy
    RETRY_MAX_ATTEMPTS: int = Field(default=3)
    RETRY_BACKOFF_FACTOR: int = Field(default=2)
    RETRY_MAX_DELAY_SECONDS: int = Field(default=30)

    # Logging
    LOG_FORMAT: str = Field(default="json")
    LOG_OUTPUT: str = Field(default="stdout")
    LOG_FILE_PATH: str = Field(default="/var/log/chatbot/app.log")
    LOG_FILE_MAX_SIZE_MB: int = Field(default=100)
    LOG_FILE_BACKUP_COUNT: int = Field(default=5)
    LOG_INCLUDE_TRACE_ID: bool = Field(default=True)

    # Sentry
    SENTRY_ENABLED: bool = Field(default=False)
    SENTRY_DSN: str = Field(default="")
    SENTRY_ENVIRONMENT: str = Field(default="development")
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1)

    # Feature Flags
    FEATURE_SEMANTIC_CACHE: bool = Field(default=True)
    FEATURE_MODEL_FALLBACK: bool = Field(default=True)
    FEATURE_USAGE_TRACKING: bool = Field(default=True)
    FEATURE_DISTRIBUTED_TRACING: bool = Field(default=True)
    FEATURE_WEBSOCKET_SUPPORT: bool = Field(default=True)
    FEATURE_STREAMING_RESPONSES: bool = Field(default=True)
    FEATURE_CONVERSATION_MEMORY: bool = Field(default=True)
    FEATURE_FUNCTION_CALLING: bool = Field(default=False)
    FEATURE_VISION_SUPPORT: bool = Field(default=False)
    FEATURE_VOICE_SUPPORT: bool = Field(default=False)

    # Email Service
    EMAIL_ENABLED: bool = Field(default=False)
    EMAIL_PROVIDER: str = Field(default="smtp")
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_USE_TLS: bool = Field(default=True)
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@ai-chatbot.com")
    EMAIL_FROM_NAME: str = Field(default="AI Chatbot System")

    # Webhook
    WEBHOOK_ENABLED: bool = Field(default=False)
    WEBHOOK_URL: str = Field(default="")
    WEBHOOK_SECRET: str = Field(default="")
    WEBHOOK_RETRY_ATTEMPTS: int = Field(default=3)
    WEBHOOK_TIMEOUT_SECONDS: int = Field(default=10)

    # Development
    DEV_MODE: bool = Field(default=False)
    DEV_AUTO_RELOAD: bool = Field(default=False)
    DEV_CORS_ALLOW_ALL: bool = Field(default=False)
    DEV_SHOW_SQL_QUERIES: bool = Field(default=False)
    DEV_PROFILE_REQUESTS: bool = Field(default=False)
    DEV_MOCK_EXTERNAL_SERVICES: bool = Field(default=False)
    TEST_DISABLE_RATE_LIMITING: bool = Field(default=False)
    TEST_DISABLE_AUTH: bool = Field(default=False)

    # Deployment
    DOCKER_REGISTRY: str = Field(default="docker.io")
    DOCKER_IMAGE_NAME: str = Field(default="ai-chatbot-api")
    DOCKER_IMAGE_TAG: str = Field(default="latest")
    K8S_NAMESPACE: str = Field(default="ai-chatbot")
    K8S_DEPLOYMENT_NAME: str = Field(default="ai-chatbot-api")
    K8S_SERVICE_NAME: str = Field(default="ai-chatbot-service")
    K8S_INGRESS_HOST: str = Field(default="api.ai-chatbot.com")

    # Cloud Provider
    CLOUD_PROVIDER: str = Field(default="aws")
    AWS_REGION: str = Field(default="us-east-1")
    AWS_ACCESS_KEY_ID: str = Field(default="")
    AWS_SECRET_ACCESS_KEY: str = Field(default="")
    AWS_S3_BUCKET: str = Field(default="")

    # Backup
    BACKUP_ENABLED: bool = Field(default=False)
    BACKUP_SCHEDULE: str = Field(default="0 2 * * *")
    BACKUP_RETENTION_DAYS: int = Field(default=30)
    BACKUP_S3_BUCKET: str = Field(default="")
    BACKUP_ENCRYPTION_KEY: str = Field(default="")

    # Compliance
    AUDIT_LOG_ENABLED: bool = Field(default=True)
    AUDIT_LOG_TABLE: str = Field(default="audit_logs")
    AUDIT_LOG_RETENTION_DAYS: int = Field(default=90)
    PII_DETECTION_ENABLED: bool = Field(default=True)
    PII_MASKING_ENABLED: bool = Field(default=True)
    GDPR_COMPLIANCE_MODE: bool = Field(default=False)
    DATA_RETENTION_DAYS: int = Field(default=365)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Allow extra fields from .env that aren't defined here
    )


settings = Settings()
