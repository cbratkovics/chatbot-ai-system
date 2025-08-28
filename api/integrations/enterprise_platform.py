"""
Enterprise Integration Platform
REST/GraphQL APIs, webhook system, SDK examples, and enterprise connectors
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import httpx
import jwt
import redis.asyncio as redis
from ariadne import QueryType, make_executable_schema
from celery import Celery
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    REST_API = "rest_api"
    GRAPHQL = "graphql"
    WEBHOOK = "webhook"
    SDK = "sdk"
    SAML_SSO = "saml_sso"
    OAUTH2 = "oauth2"
    LDAP = "ldap"
    SCIM = "scim"


class WebhookEvent(Enum):
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    SYSTEM_ALERT = "system.alert"
    COMPLIANCE_VIOLATION = "compliance.violation"


class AuthenticationMethod(Enum):
    API_KEY = "api_key"
    JWT_BEARER = "jwt_bearer"
    OAUTH2 = "oauth2"
    SAML = "saml"
    BASIC_AUTH = "basic_auth"
    MUTUAL_TLS = "mutual_tls"


# Pydantic models for REST API
class ChatSessionCreate(BaseModel):
    model: str = Field(..., description="AI model to use")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1000, ge=1, le=32000)
    system_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionResponse(BaseModel):
    id: str
    user_id: str
    status: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    message_count: int
    total_tokens: int
    total_cost: float


class MessageSend(BaseModel):
    content: str = Field(..., max_length=32000)
    stream: bool = False
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    attachments: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: datetime


class WebhookConfig(BaseModel):
    url: str = Field(..., description="Webhook endpoint URL")
    events: list[WebhookEvent] = Field(..., description="Events to subscribe to")
    secret: str | None = Field(None, description="Secret for signature verification")
    headers: dict[str, str] = Field(default_factory=dict)
    retry_count: int = Field(3, ge=0, le=10)
    timeout: int = Field(30, ge=1, le=300)
    active: bool = True


@dataclass
class APIKey:
    id: str
    key: str
    name: str
    scopes: list[str]
    rate_limit: int
    created_at: datetime
    expires_at: datetime | None
    last_used: datetime | None
    is_active: bool


@dataclass
class WebhookDelivery:
    id: str
    webhook_id: str
    event: WebhookEvent
    payload: dict[str, Any]
    url: str
    status_code: int | None
    response_body: str | None
    attempts: int
    delivered_at: datetime | None
    failed: bool
    error_message: str | None


# SQLAlchemy models
Base = declarative_base()


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    integration_type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String)
    events = Column(JSON, nullable=False)
    headers = Column(JSON)
    retry_count = Column(Integer, default=3)
    timeout = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String, primary_key=True)
    webhook_id = Column(String, nullable=False)
    event = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    url = Column(String, nullable=False)
    status_code = Column(Integer)
    response_body = Column(Text)
    attempts = Column(Integer, default=0)
    delivered_at = Column(DateTime)
    failed = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EnterpriseIntegrationPlatform:
    """
    Comprehensive enterprise integration platform with multiple protocols and standards
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

        # Database
        self.engine = create_engine(config["database_url"])
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Redis for caching and job queues
        self.redis = redis.from_url(config["redis_url"])

        # Celery for background tasks
        self.celery = Celery("enterprise_integration")
        self.celery.conf.update(
            broker_url=config["redis_url"],
            result_backend=config["redis_url"],
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
        )

        # FastAPI app for REST API
        self.rest_app = FastAPI(
            title="AI Chatbot Enterprise API",
            description="Enterprise-grade REST API for AI chatbot system",
            version="2.0.0",
        )

        # GraphQL schema
        self.graphql_schema = None

        # Webhook management
        self.webhook_endpoints: dict[str, WebhookConfig] = {}
        self.webhook_queue = asyncio.Queue()

        # API key management
        self.api_keys: dict[str, APIKey] = {}

        # Rate limiting
        self.rate_limiters: dict[str, dict[str, Any]] = {}

        # Setup FastAPI
        self._setup_fastapi()

        # Setup GraphQL
        self._setup_graphql()

        # Setup webhooks
        self._setup_webhooks()

    async def initialize(self):
        """Initialize the integration platform"""

        # Load API keys
        await self._load_api_keys()

        # Load webhook configurations
        await self._load_webhook_configs()

        # Start background tasks
        asyncio.create_task(self._webhook_delivery_worker())
        asyncio.create_task(self._webhook_retry_worker())
        asyncio.create_task(self._cleanup_old_deliveries())

        logger.info("Enterprise Integration Platform initialized")

    def _setup_fastapi(self):
        """Setup FastAPI application with all endpoints"""

        # CORS middleware
        self.rest_app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.get("cors_origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Authentication dependency
        security = HTTPBearer()

        async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
            """Authenticate API requests"""
            return await self._authenticate_request(credentials.credentials)

        # Chat Sessions API
        @self.rest_app.post("/api/v2/chat/sessions", response_model=ChatSessionResponse)
        async def create_chat_session(session: ChatSessionCreate, user=Depends(get_current_user)):
            """Create a new chat session"""
            try:
                # Create session logic here
                session_id = str(uuid.uuid4())

                session_data = {
                    "id": session_id,
                    "user_id": user["user_id"],
                    "status": "active",
                    "config": {
                        "model": session.model,
                        "temperature": session.temperature,
                        "max_tokens": session.max_tokens,
                        "system_prompt": session.system_prompt,
                    },
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                    "message_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }

                # Store in database
                await self._store_session(session_data)

                # Trigger webhook
                await self._trigger_webhook(
                    WebhookEvent.SESSION_STARTED,
                    {
                        "session_id": session_id,
                        "user_id": user["user_id"],
                        "config": session_data["config"],
                    },
                )

                return ChatSessionResponse(**session_data)

            except Exception as e:
                logger.error(f"Session creation error: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.rest_app.get("/api/v2/chat/sessions/{session_id}", response_model=ChatSessionResponse)
        async def get_chat_session(session_id: str, user=Depends(get_current_user)):
            """Get chat session details"""
            try:
                session_data = await self._get_session(session_id, user["user_id"])
                if not session_data:
                    raise HTTPException(status_code=404, detail="Session not found")

                return ChatSessionResponse(**session_data)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Session retrieval error: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.rest_app.post(
            "/api/v2/chat/sessions/{session_id}/messages", response_model=MessageResponse
        )
        async def send_message(
            session_id: str, message: MessageSend, user=Depends(get_current_user)
        ):
            """Send a message in chat session"""
            try:
                # Validate session
                session_data = await self._get_session(session_id, user["user_id"])
                if not session_data:
                    raise HTTPException(status_code=404, detail="Session not found")

                # Process message
                message_id = str(uuid.uuid4())

                # This would integrate with the AI service
                ai_response = await self._process_ai_message(
                    session_data, message.content, message.context
                )

                message_data = {
                    "id": message_id,
                    "session_id": session_id,
                    "role": "assistant",
                    "content": ai_response["content"],
                    "attachments": [],
                    "metadata": {
                        "model": session_data["config"]["model"],
                        "tokens": ai_response.get("tokens", 0),
                        "cost": ai_response.get("cost", 0.0),
                        "response_time": ai_response.get("response_time", 0.0),
                    },
                    "created_at": datetime.now(UTC),
                }

                # Store message
                await self._store_message(message_data)

                # Trigger webhook
                await self._trigger_webhook(
                    WebhookEvent.MESSAGE_SENT,
                    {
                        "message_id": message_id,
                        "session_id": session_id,
                        "content": message_data["content"],
                        "metadata": message_data["metadata"],
                    },
                )

                return MessageResponse(**message_data)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        # Webhook Management API
        @self.rest_app.post("/api/v2/webhooks")
        async def create_webhook(webhook: WebhookConfig, user=Depends(get_current_user)):
            """Create webhook endpoint"""
            try:
                webhook_id = str(uuid.uuid4())

                # Store webhook configuration
                db = self.SessionLocal()
                try:
                    webhook_endpoint = WebhookEndpoint(
                        id=webhook_id,
                        user_id=user["user_id"],
                        url=webhook.url,
                        secret=webhook.secret,
                        events=[event.value for event in webhook.events],
                        headers=webhook.headers,
                        retry_count=webhook.retry_count,
                        timeout=webhook.timeout,
                        is_active=webhook.active,
                    )
                    db.add(webhook_endpoint)
                    db.commit()

                    return {"webhook_id": webhook_id, "status": "created"}

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Webhook creation error: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.rest_app.get("/api/v2/webhooks")
        async def list_webhooks(user=Depends(get_current_user)):
            """List user's webhooks"""
            try:
                db = self.SessionLocal()
                try:
                    webhooks = (
                        db.query(WebhookEndpoint)
                        .filter(WebhookEndpoint.user_id == user["user_id"])
                        .all()
                    )

                    return {
                        "webhooks": [
                            {
                                "id": wh.id,
                                "url": wh.url,
                                "events": wh.events,
                                "is_active": wh.is_active,
                                "created_at": wh.created_at.isoformat(),
                            }
                            for wh in webhooks
                        ]
                    }

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Webhook listing error: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        # Analytics API
        @self.rest_app.get("/api/v2/analytics/usage")
        async def get_usage_analytics(
            start_date: str, end_date: str, user=Depends(get_current_user)
        ):
            """Get usage analytics"""
            try:
                # Parse dates
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)

                # Generate analytics
                analytics = await self._generate_usage_analytics(user["user_id"], start, end)

                return analytics

            except Exception as e:
                logger.error(f"Analytics error: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        # Health check
        @self.rest_app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "version": "2.0.0",
            }

    def _setup_graphql(self):
        """Setup GraphQL schema and resolvers"""

        # Define GraphQL schema
        type_defs = """
            type Query {
                chatSessions(limit: Int, offset: Int): [ChatSession!]!
                chatSession(id: String!): ChatSession
                messages(sessionId: String!, limit: Int, offset: Int): [Message!]!
                usageAnalytics(startDate: String!, endDate: String!): UsageAnalytics!
            }
            
            type Mutation {
                createChatSession(input: CreateChatSessionInput!): ChatSession!
                sendMessage(sessionId: String!, input: SendMessageInput!): Message!
                updateChatSession(id: String!, input: UpdateChatSessionInput!): ChatSession!
            }
            
            type ChatSession {
                id: String!
                userId: String!
                status: String!
                config: SessionConfig!
                createdAt: String!
                updatedAt: String!
                messageCount: Int!
                totalTokens: Int!
                totalCost: Float!
                messages: [Message!]!
            }
            
            type Message {
                id: String!
                sessionId: String!
                role: String!
                content: String!
                attachments: [Attachment!]!
                metadata: MessageMetadata!
                createdAt: String!
            }
            
            type SessionConfig {
                model: String!
                temperature: Float!
                maxTokens: Int!
                systemPrompt: String
            }
            
            type Attachment {
                type: String!
                url: String!
                filename: String
                size: Int
            }
            
            type MessageMetadata {
                model: String
                tokens: Int
                cost: Float
                responseTime: Float
                qualityScore: Float
            }
            
            type UsageAnalytics {
                totalRequests: Int!
                totalTokens: Int!
                totalCost: Float!
                averageResponseTime: Float!
                successRate: Float!
                breakdowns: UsageBreakdowns!
            }
            
            type UsageBreakdowns {
                byModel: [ModelUsage!]!
                byDay: [DailyUsage!]!
            }
            
            type ModelUsage {
                model: String!
                requests: Int!
                tokens: Int!
                cost: Float!
            }
            
            type DailyUsage {
                date: String!
                requests: Int!
                tokens: Int!
                cost: Float!
            }
            
            input CreateChatSessionInput {
                model: String!
                temperature: Float = 0.7
                maxTokens: Int = 1000
                systemPrompt: String
                metadata: String
            }
            
            input SendMessageInput {
                content: String!
                stream: Boolean = false
                attachments: [AttachmentInput!]
                context: String
            }
            
            input UpdateChatSessionInput {
                status: String
                config: SessionConfigInput
            }
            
            input SessionConfigInput {
                temperature: Float
                maxTokens: Int
                systemPrompt: String
            }
            
            input AttachmentInput {
                type: String!
                url: String!
                filename: String
                size: Int
            }
        """

        # Query resolvers
        query = QueryType()

        @query.field("chatSessions")
        async def resolve_chat_sessions(_, info, limit=20, offset=0):
            user = info.context["user"]
            return await self._get_user_sessions(user["user_id"], limit, offset)

        @query.field("chatSession")
        async def resolve_chat_session(_, info, id):
            user = info.context["user"]
            return await self._get_session(id, user["user_id"])

        @query.field("messages")
        async def resolve_messages(_, info, sessionId, limit=50, offset=0):
            user = info.context["user"]
            return await self._get_session_messages(sessionId, user["user_id"], limit, offset)

        @query.field("usageAnalytics")
        async def resolve_usage_analytics(_, info, startDate, endDate):
            user = info.context["user"]
            start = datetime.fromisoformat(startDate)
            end = datetime.fromisoformat(endDate)
            return await self._generate_usage_analytics(user["user_id"], start, end)

        # Create executable schema
        self.graphql_schema = make_executable_schema(type_defs, query)

    def _setup_webhooks(self):
        """Setup webhook delivery system"""

        @self.celery.task
        def deliver_webhook(webhook_id: str, event: str, payload: dict[str, Any]):
            """Celery task for webhook delivery"""
            asyncio.run(self._deliver_webhook_task(webhook_id, event, payload))

        self.deliver_webhook_task = deliver_webhook

    async def _authenticate_request(self, token: str) -> dict[str, Any]:
        """Authenticate API request"""
        try:
            # Check if it's an API key
            if token.startswith("sk_"):
                api_key = self.api_keys.get(token)
                if not api_key or not api_key.is_active:
                    raise HTTPException(status_code=401, detail="Invalid API key")

                # Check rate limits
                if not await self._check_rate_limit(api_key):
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")

                return {"user_id": api_key.id, "auth_method": "api_key", "scopes": api_key.scopes}

            # Check if it's a JWT token
            else:
                payload = jwt.decode(token, self.config["jwt_secret"], algorithms=["HS256"])

                return {
                    "user_id": payload.get("user_id"),
                    "auth_method": "jwt",
                    "scopes": payload.get("scopes", []),
                }

        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token") from None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed") from e

    async def _check_rate_limit(self, api_key: APIKey) -> bool:
        """Check API key rate limits"""
        try:
            current_time = time.time()
            window_size = 3600  # 1 hour

            rate_key = f"rate_limit:{api_key.id}"

            # Get current usage
            usage = await self.redis.hgetall(rate_key)

            if usage:
                window_start = float(usage.get("window_start", 0))
                request_count = int(usage.get("count", 0))

                if current_time - window_start < window_size:
                    if request_count >= api_key.rate_limit:
                        return False
                    else:
                        await self.redis.hincrby(rate_key, "count", 1)
                        await self.redis.expire(rate_key, window_size)
                else:
                    # New window
                    await self.redis.hset(
                        rate_key, mapping={"window_start": current_time, "count": 1}
                    )
                    await self.redis.expire(rate_key, window_size)
            else:
                # First request
                await self.redis.hset(rate_key, mapping={"window_start": current_time, "count": 1})
                await self.redis.expire(rate_key, window_size)

            return True

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True  # Allow on error

    async def _trigger_webhook(self, event: WebhookEvent, payload: dict[str, Any]):
        """Trigger webhook delivery"""
        try:
            # Find matching webhook endpoints
            db = self.SessionLocal()
            try:
                webhooks = (
                    db.query(WebhookEndpoint)
                    .filter(
                        WebhookEndpoint.is_active.is_(True),
                        WebhookEndpoint.events.contains([event.value]),
                    )
                    .all()
                )

                # Queue webhook deliveries
                for webhook in webhooks:
                    delivery_id = str(uuid.uuid4())

                    delivery = WebhookDeliveryLog(
                        id=delivery_id,
                        webhook_id=webhook.id,
                        event=event.value,
                        payload=payload,
                        url=webhook.url,
                    )
                    db.add(delivery)

                    # Queue for delivery
                    await self.webhook_queue.put(
                        {
                            "delivery_id": delivery_id,
                            "webhook_id": webhook.id,
                            "url": webhook.url,
                            "secret": webhook.secret,
                            "headers": webhook.headers or {},
                            "timeout": webhook.timeout,
                            "event": event.value,
                            "payload": payload,
                        }
                    )

                db.commit()

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Webhook trigger error: {e}")

    async def _webhook_delivery_worker(self):
        """Background worker for webhook delivery"""
        while True:
            try:
                # Get webhook from queue
                webhook_data = await self.webhook_queue.get()

                # Deliver webhook
                await self._deliver_webhook(webhook_data)

            except Exception as e:
                logger.error(f"Webhook delivery worker error: {e}")
                await asyncio.sleep(1)

    async def _deliver_webhook(self, webhook_data: dict[str, Any]):
        """Deliver webhook to endpoint"""
        try:
            delivery_id = webhook_data["delivery_id"]
            url = webhook_data["url"]
            secret = webhook_data["secret"]
            headers = webhook_data["headers"]
            timeout = webhook_data["timeout"]
            payload = webhook_data["payload"]
            event = webhook_data["event"]

            # Prepare payload
            webhook_payload = {
                "event": event,
                "timestamp": datetime.now(UTC).isoformat(),
                "data": payload,
            }

            # Generate signature if secret provided
            if secret:
                signature = hmac.new(
                    secret.encode(), json.dumps(webhook_payload).encode(), hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            # Set default headers
            headers.update(
                {"Content-Type": "application/json", "User-Agent": "AI-Chatbot-Webhook/1.0"}
            )

            # Make HTTP request
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=webhook_payload, headers=headers)

                # Update delivery status
                db = self.SessionLocal()
                try:
                    delivery = (
                        db.query(WebhookDeliveryLog)
                        .filter(WebhookDeliveryLog.id == delivery_id)
                        .first()
                    )

                    if delivery:
                        delivery.status_code = response.status_code
                        delivery.response_body = response.text[:1000]  # Limit size
                        delivery.attempts += 1

                        if 200 <= response.status_code < 300:
                            delivery.delivered_at = datetime.now(UTC)
                            delivery.failed = False
                        else:
                            delivery.failed = True
                            delivery.error_message = f"HTTP {response.status_code}"

                        db.commit()

                finally:
                    db.close()

                logger.info(f"Webhook delivered to {url}: {response.status_code}")

        except Exception as e:
            logger.error(f"Webhook delivery error: {e}")

            # Mark delivery as failed
            db = self.SessionLocal()
            try:
                delivery = (
                    db.query(WebhookDeliveryLog)
                    .filter(WebhookDeliveryLog.id == webhook_data["delivery_id"])
                    .first()
                )

                if delivery:
                    delivery.failed = True
                    delivery.error_message = str(e)
                    delivery.attempts += 1
                    db.commit()

            finally:
                db.close()

    async def _webhook_retry_worker(self):
        """Background worker for webhook retries"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                # Find failed deliveries to retry
                db = self.SessionLocal()
                try:
                    failed_deliveries = (
                        db.query(WebhookDeliveryLog)
                        .filter(
                            WebhookDeliveryLog.failed.is_(True),
                            WebhookDeliveryLog.attempts < 3,
                            WebhookDeliveryLog.created_at > datetime.utcnow() - timedelta(hours=24),
                        )
                        .limit(100)
                        .all()
                    )

                    for delivery in failed_deliveries:
                        # Get webhook config
                        webhook = (
                            db.query(WebhookEndpoint)
                            .filter(WebhookEndpoint.id == delivery.webhook_id)
                            .first()
                        )

                        if webhook and webhook.is_active:
                            # Queue for retry
                            await self.webhook_queue.put(
                                {
                                    "delivery_id": delivery.id,
                                    "webhook_id": webhook.id,
                                    "url": webhook.url,
                                    "secret": webhook.secret,
                                    "headers": webhook.headers or {},
                                    "timeout": webhook.timeout,
                                    "event": delivery.event,
                                    "payload": delivery.payload,
                                }
                            )

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Webhook retry worker error: {e}")

    async def _cleanup_old_deliveries(self):
        """Cleanup old webhook deliveries"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily cleanup

                cutoff_date = datetime.utcnow() - timedelta(days=30)

                db = self.SessionLocal()
                try:
                    deleted_count = (
                        db.query(WebhookDeliveryLog)
                        .filter(WebhookDeliveryLog.created_at < cutoff_date)
                        .delete()
                    )

                    db.commit()

                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old webhook deliveries")

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Webhook cleanup error: {e}")

    async def _load_api_keys(self):
        """Load API keys from database"""
        try:
            # This would load from database
            # For now, create sample API keys
            sample_key = APIKey(
                id="user_123",
                key="sk_test_1234567890abcdef",
                name="Test API Key",
                scopes=["chat:read", "chat:write", "analytics:read"],
                rate_limit=1000,
                created_at=datetime.now(UTC),
                expires_at=None,
                last_used=None,
                is_active=True,
            )

            self.api_keys[sample_key.key] = sample_key

        except Exception as e:
            logger.error(f"API key loading error: {e}")

    async def _load_webhook_configs(self):
        """Load webhook configurations from database"""
        try:
            db = self.SessionLocal()
            try:
                webhooks = db.query(WebhookEndpoint).filter(WebhookEndpoint.is_active.is_(True)).all()

                for webhook in webhooks:
                    self.webhook_endpoints[webhook.id] = WebhookConfig(
                        url=webhook.url,
                        events=[WebhookEvent(event) for event in webhook.events],
                        secret=webhook.secret,
                        headers=webhook.headers or {},
                        retry_count=webhook.retry_count,
                        timeout=webhook.timeout,
                        active=webhook.is_active,
                    )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Webhook config loading error: {e}")

    async def _store_session(self, session_data: dict[str, Any]):
        """Store chat session in database"""
        try:
            # Store session data
            await self.redis.setex(
                f"session:{session_data['id']}",
                3600 * 24,  # 24 hours
                json.dumps(session_data, default=str),
            )

        except Exception as e:
            logger.error(f"Session storage error: {e}")

    async def _get_session(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """Get chat session data"""
        try:
            session_data = await self.redis.get(f"session:{session_id}")
            if session_data:
                session = json.loads(session_data)
                if session.get("user_id") == user_id:
                    return session
            return None

        except Exception as e:
            logger.error(f"Session retrieval error: {e}")
            return None

    async def _store_message(self, message_data: dict[str, Any]):
        """Store message in database"""
        try:
            # Store message
            await self.redis.lpush(
                f"messages:{message_data['session_id']}", json.dumps(message_data, default=str)
            )

            # Set TTL
            await self.redis.expire(f"messages:{message_data['session_id']}", 3600 * 24 * 7)

        except Exception as e:
            logger.error(f"Message storage error: {e}")

    async def _process_ai_message(
        self, session_data: dict[str, Any], content: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Process message with AI service"""
        try:
            # This would integrate with the actual AI service
            # For now, return mock response

            response_content = f"I received your message: {content[:100]}..."

            return {
                "content": response_content,
                "tokens": len(content.split()) + len(response_content.split()),
                "cost": 0.002,
                "response_time": 1.5,
                "model": session_data["config"]["model"],
            }

        except Exception as e:
            logger.error(f"AI message processing error: {e}")
            return {
                "content": "I'm sorry, I encountered an error processing your message.",
                "tokens": 0,
                "cost": 0.0,
                "response_time": 0.0,
                "model": "error",
            }

    async def _get_user_sessions(
        self, user_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        """Get user's chat sessions"""
        try:
            # This would query the database for user sessions
            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"User sessions retrieval error: {e}")
            return []

    async def _get_session_messages(
        self, session_id: str, user_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        """Get messages for a session"""
        try:
            # Verify session ownership
            session = await self._get_session(session_id, user_id)
            if not session:
                return []

            # Get messages
            messages = await self.redis.lrange(f"messages:{session_id}", offset, offset + limit - 1)

            return [json.loads(msg) for msg in messages]

        except Exception as e:
            logger.error(f"Session messages retrieval error: {e}")
            return []

    async def _generate_usage_analytics(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Generate usage analytics for user"""
        try:
            # This would generate real analytics from database
            # For now, return mock data

            return {
                "total_requests": 1250,
                "total_tokens": 45000,
                "total_cost": 67.50,
                "average_response_time": 1.8,
                "success_rate": 0.995,
                "breakdowns": {
                    "by_model": [
                        {"model": "gpt-4", "requests": 800, "tokens": 30000, "cost": 45.00},
                        {"model": "gpt-3.5-turbo", "requests": 450, "tokens": 15000, "cost": 22.50},
                    ],
                    "by_day": [
                        {"date": "2024-01-01", "requests": 50, "tokens": 1800, "cost": 2.70},
                        {"date": "2024-01-02", "requests": 75, "tokens": 2700, "cost": 4.05},
                    ],
                },
            }

        except Exception as e:
            logger.error(f"Analytics generation error: {e}")
            return {}

    def generate_sdk_examples(self) -> dict[str, str]:
        """Generate SDK examples for different languages"""

        examples = {
            "python": """
# Python SDK Example
import requests

class ChatbotAPI:
    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def create_session(self, model: str = "gpt-4", temperature: float = 0.7):
        response = requests.post(
            f"{self.base_url}/api/v2/chat/sessions",
            headers=self.headers,
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": 1000
            }
        )
        return response.json()
    
    def send_message(self, session_id: str, content: str):
        response = requests.post(
            f"{self.base_url}/api/v2/chat/sessions/{session_id}/messages",
            headers=self.headers,
            json={"content": content}
        )
        return response.json()

# Usage
api = ChatbotAPI("sk_your_api_key_here")
session = api.create_session()
message = api.send_message(session["id"], "Hello, world!")
print(message["content"])
            """,
            "javascript": """
// JavaScript SDK Example
class ChatbotAPI {
    constructor(apiKey, baseUrl = 'https://api.example.com') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }
    
    async createSession(model = 'gpt-4', temperature = 0.7) {
        const response = await fetch(`${this.baseUrl}/api/v2/chat/sessions`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                model,
                temperature,
                max_tokens: 1000
            })
        });
        return response.json();
    }
    
    async sendMessage(sessionId, content) {
        const response = await fetch(`${this.baseUrl}/api/v2/chat/sessions/${sessionId}/messages`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ content })
        });
        return response.json();
    }
}

// Usage
const api = new ChatbotAPI('sk_your_api_key_here');
const session = await api.createSession();
const message = await api.sendMessage(session.id, 'Hello, world!');
console.log(message.content);
            """,
            "curl": """
# cURL Examples

# Create a chat session
curl -X POST https://api.example.com/api/v2/chat/sessions \\
  -H "Authorization: Bearer sk_your_api_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 1000
  }'

# Send a message
curl -X POST https://api.example.com/api/v2/chat/sessions/SESSION_ID/messages \\
  -H "Authorization: Bearer sk_your_api_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "Hello, world!"
  }'

# Get usage analytics
curl -X GET "https://api.example.com/api/v2/analytics/usage?start_date=2024-01-01&end_date=2024-01-31" \\
  -H "Authorization: Bearer sk_your_api_key_here"
            """,
            "graphql": """
# GraphQL Examples

# Query for chat sessions
query GetChatSessions {
  chatSessions(limit: 10, offset: 0) {
    id
    status
    config {
      model
      temperature
    }
    messageCount
    totalCost
    createdAt
  }
}

# Mutation to create session
mutation CreateChatSession {
  createChatSession(input: {
    model: "gpt-4"
    temperature: 0.7
    maxTokens: 1000
    systemPrompt: "You are a helpful assistant"
  }) {
    id
    status
    config {
      model
      temperature
    }
  }
}

# Mutation to send message
mutation SendMessage {
  sendMessage(
    sessionId: "session_id_here"
    input: {
      content: "Hello, world!"
      stream: false
    }
  ) {
    id
    content
    metadata {
      tokens
      cost
      responseTime
    }
  }
}
            """,
        }

        return examples

    async def create_saml_sso_config(self, user_id: str, config: dict[str, Any]) -> str:
        """Create SAML SSO configuration"""
        try:
            config_id = str(uuid.uuid4())

            # Store SAML configuration
            db = self.SessionLocal()
            try:
                saml_config = IntegrationConfig(
                    id=config_id,
                    user_id=user_id,
                    integration_type=IntegrationType.SAML_SSO.value,
                    name=config.get("name", "SAML SSO"),
                    config=config,
                )
                db.add(saml_config)
                db.commit()

                return config_id

            finally:
                db.close()

        except Exception as e:
            logger.error(f"SAML SSO config creation error: {e}")
            raise

    async def create_scim_provisioning(self, user_id: str, config: dict[str, Any]) -> str:
        """Create SCIM user provisioning configuration"""
        try:
            config_id = str(uuid.uuid4())

            # Store SCIM configuration
            db = self.SessionLocal()
            try:
                scim_config = IntegrationConfig(
                    id=config_id,
                    user_id=user_id,
                    integration_type=IntegrationType.SCIM.value,
                    name=config.get("name", "SCIM Provisioning"),
                    config=config,
                )
                db.add(scim_config)
                db.commit()

                return config_id

            finally:
                db.close()

        except Exception as e:
            logger.error(f"SCIM config creation error: {e}")
            raise

    async def shutdown(self):
        """Shutdown the integration platform"""
        try:
            # Close Redis connection
            await self.redis.close()

            logger.info("Enterprise Integration Platform shut down")

        except Exception as e:
            logger.error(f"Shutdown error: {e}")


# Example usage and configuration
def create_integration_platform(config: dict[str, Any]) -> EnterpriseIntegrationPlatform:
    """Create and configure the integration platform"""

    platform = EnterpriseIntegrationPlatform(config)

    # Add custom middleware, authentication, etc.

    return platform
