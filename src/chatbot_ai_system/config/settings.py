"""Settings configuration"""
import json
from typing import List, Optional, Tuple
from pydantic import AliasChoices, Field, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with complete configuration"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_assignment=True,
        # Fields declare env aliases; allow Settings(field_name=...) too, so tests and
        # programmatic construction are not silently ignored.
        populate_by_name=True,
    )

    # Application
    app_name: str = Field(default="AI Chatbot System", validation_alias="APP_NAME")
    version: str = "1.0.0"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_prefix: str = Field(default="/api/v1", validation_alias="API_PREFIX")
    api_base_url: Optional[str] = Field(
        default="http://localhost:8000", validation_alias="API_BASE_URL"
    )

    # Server
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT", ge=1, le=65535)
    workers: int = Field(default=1, validation_alias="WORKERS", ge=1)
    reload: bool = Field(default=False, validation_alias="RELOAD")

    # API Keys
    openai_api_key: Optional[SecretStr] = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[SecretStr] = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )
    groq_api_key: Optional[SecretStr] = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", validation_alias="GROQ_BASE_URL"
    )

    # Redis (optional: unset or unreachable -> in-process memory cache)
    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    cache_connect_timeout_seconds: float = Field(
        default=2.0, validation_alias="CACHE_CONNECT_TIMEOUT_SECONDS"
    )
    memory_cache_max_entries: int = Field(default=512, validation_alias="MEMORY_CACHE_MAX_ENTRIES")
    redis_max_connections: int = Field(default=50, validation_alias="REDIS_MAX_CONNECTIONS")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, validation_alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, validation_alias="RATE_LIMIT_PERIOD")

    api_key: Optional[str] = Field(default=None, validation_alias="API_KEY")
    # Cache
    cache_enabled: bool = Field(default=True, validation_alias="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(
        default=3600, validation_alias=AliasChoices("CACHE_TTL_SECONDS", "CACHE_TTL")
    )
    # F1-optimal threshold from the cache paraphrase eval sweep (evals/results/latest.json,
    # text-embedding-3-small, 68 pairs, run 2026-09-09). Change it by re-running `make evals`.
    semantic_cache_threshold: float = Field(
        default=0.76, validation_alias="SEMANTIC_CACHE_THRESHOLD"
    )
    cache_compression_enabled: bool = Field(
        default=False, validation_alias="CACHE_COMPRESSION_ENABLED"
    )
    cache_compression_threshold: int = Field(
        default=1024, validation_alias="CACHE_COMPRESSION_THRESHOLD"
    )
    # Semantic (paraphrase) matching on the demo path, ADR 0007: exact-key lookup first, then
    # OpenAI embeddings compared in an in-process index. Threshold is set from the eval sweep
    # in evals/results/latest.json, not by hand.
    semantic_cache_enabled: bool = Field(default=False, validation_alias="SEMANTIC_CACHE_ENABLED")
    semantic_cache_max_entries: int = Field(
        default=512, validation_alias="SEMANTIC_CACHE_MAX_ENTRIES"
    )
    semantic_cache_embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="SEMANTIC_CACHE_EMBEDDING_MODEL"
    )
    semantic_cache_embedding_timeout_seconds: float = Field(
        default=5.0, validation_alias="SEMANTIC_CACHE_EMBEDDING_TIMEOUT_SECONDS"
    )
    # Committed eval artifact served by GET /api/v1/evals/latest; defaults to the repo file.
    evals_results_path: Optional[str] = Field(default=None, validation_alias="EVALS_RESULTS_PATH")
    cache_circuit_breaker_enabled: bool = Field(
        default=True, validation_alias="CACHE_CIRCUIT_BREAKER_ENABLED"
    )
    cache_warming_enabled: bool = Field(default=False, validation_alias="CACHE_WARMING_ENABLED")

    # Model Defaults
    default_model: str = Field(default="gpt-4o-mini", validation_alias="DEFAULT_MODEL")
    default_temperature: float = Field(default=0.7, validation_alias="DEFAULT_TEMPERATURE")
    default_max_tokens: int = Field(default=2048, validation_alias="DEFAULT_MAX_TOKENS")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    anthropic_model: str = Field(
        default="claude-3-5-haiku-latest", validation_alias="ANTHROPIC_MODEL"
    )
    groq_model: str = Field(default="openai/gpt-oss-20b", validation_alias="GROQ_MODEL")
    # Comma-separated "provider:model" pairs tried in order after the primary fails.
    fallback_models: str = Field(
        default="groq:openai/gpt-oss-20b", validation_alias="FALLBACK_MODELS"
    )
    default_provider: str = Field(default="openai", validation_alias="DEFAULT_PROVIDER")
    enable_fallback: bool = Field(default=True, validation_alias="ENABLE_FALLBACK")
    max_retries: int = Field(default=2, validation_alias="MAX_RETRIES")

    # Demo guardrails (in-process, no database)
    demo_guardrails_enabled: bool = Field(default=True, validation_alias="DEMO_GUARDRAILS_ENABLED")
    demo_rate_limit_per_minute: int = Field(
        default=10, validation_alias="DEMO_RATE_LIMIT_PER_MINUTE"
    )
    demo_rate_limit_per_day: int = Field(default=40, validation_alias="DEMO_RATE_LIMIT_PER_DAY")
    demo_max_tokens: int = Field(default=400, validation_alias="DEMO_MAX_TOKENS")
    demo_max_history_messages: int = Field(
        default=8, validation_alias="DEMO_MAX_HISTORY_MESSAGES"
    )
    demo_daily_token_budget: int = Field(
        default=150_000, validation_alias="DEMO_DAILY_TOKEN_BUDGET"
    )
    # Demo-only failover switch. When the toggle is enabled, a request carrying the header
    # X-Demo-Simulate-Failure: 1 makes the primary provider fail with a 503 before it is called.
    demo_failure_toggle_enabled: bool = Field(
        default=False, validation_alias="DEMO_FAILURE_TOGGLE_ENABLED"
    )
    demo_simulate_primary_failure: bool = Field(
        default=False, validation_alias="DEMO_SIMULATE_PRIMARY_FAILURE"
    )

    # Database
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    # WebSocket
    ws_max_connections: int = Field(default=100, validation_alias="WS_MAX_CONNECTIONS")
    ws_heartbeat_interval: int = Field(default=30, validation_alias="WS_HEARTBEAT_INTERVAL")

    # Security
    jwt_secret_key: Optional[SecretStr] = Field(default=None, validation_alias="JWT_SECRET_KEY")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], validation_alias="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, validation_alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(default=["*"], validation_alias="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default=["*"], validation_alias="CORS_ALLOW_HEADERS")

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Timeouts
    request_timeout: int = Field(default=30, validation_alias="REQUEST_TIMEOUT")
    max_context_length: int = Field(default=8000, validation_alias="MAX_CONTEXT_LENGTH")
    max_tokens: int = Field(default=4000, validation_alias="MAX_TOKENS")

    # Vector Database - Pinecone Configuration
    pinecone_api_key: Optional[SecretStr] = Field(default=None, validation_alias="PINECONE_API_KEY")
    pinecone_environment: str = Field(default="us-east-1", validation_alias="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(
        default="chatbot-ai-system", validation_alias="PINECONE_INDEX_NAME"
    )
    pinecone_dimension: int = Field(default=1536, validation_alias="PINECONE_DIMENSION")
    pinecone_metric: str = Field(default="cosine", validation_alias="PINECONE_METRIC")
    pinecone_namespace: str = Field(default="default", validation_alias="PINECONE_NAMESPACE")
    enable_vector_search: bool = Field(default=False, validation_alias="ENABLE_VECTOR_SEARCH")
    vector_search_top_k: int = Field(default=5, validation_alias="VECTOR_SEARCH_TOP_K")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle JSON array format
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Handle comma-separated format
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v):
        if isinstance(v, str):
            # Handle JSON array format
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Handle comma-separated format
            return [method.strip() for method in v.split(",")]
        return v

    @field_validator("cors_allow_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v):
        if isinstance(v, str):
            # Handle JSON array format
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Handle comma-separated format or wildcard
            if v == "*":
                return ["*"]
            return [header.strip() for header in v.split(",")]
        return v

    # Properties
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_groq_key(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def configured_providers(self) -> List[str]:
        names = []
        if self.has_openai_key:
            names.append("openai")
        if self.has_anthropic_key:
            names.append("anthropic")
        if self.has_groq_key:
            names.append("groq")
        return names

    @property
    def fallback_chain(self) -> List[Tuple[str, str]]:
        """Parse FALLBACK_MODELS into (provider, model) pairs; malformed entries are dropped.

        Model ids go through the catalogue's legacy aliases, so a retired id in an old env
        file (``groq:llama-3.1-8b-instant``) resolves to its replacement instead of 404ing.
        """
        from ..providers.catalog import resolve_model

        pairs: List[Tuple[str, str]] = []
        for item in (self.fallback_models or "").split(","):
            item = item.strip()
            if ":" in item:
                provider, model = item.split(":", 1)
                if provider.strip() and model.strip():
                    pairs.append((provider.strip(), resolve_model(model.strip())))
        return pairs

    @property
    def has_pinecone_key(self) -> bool:
        return bool(self.pinecone_api_key)

    @property
    def is_vector_search_enabled(self) -> bool:
        return self.enable_vector_search and self.has_pinecone_key and self.has_openai_key


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
