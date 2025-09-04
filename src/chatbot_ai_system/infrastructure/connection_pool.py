"""
Connection Pooling and Retry Logic Implementation
Provides resilient connection management with automatic retries and circuit breaking
"""

import asyncio
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

import aiohttp
import aioredis
from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
current_region = ContextVar("current_region", default="us-east-1")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class PoolConfig:
    min_size: int = 10
    max_size: int = 100
    connection_timeout: float = 5.0
    idle_timeout: float = 300.0
    max_retries: int = 3
    retry_delay: float = 0.1
    circuit_breaker_threshold: float = 0.5
    circuit_breaker_timeout: float = 60.0


class CircuitBreaker:
    """Circuit breaker pattern implementation"""

    def __init__(
        self, failure_threshold: float = 0.5, timeout: float = 60.0, window_size: int = 100
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.window_size = window_size
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = 0
        self.calls = []

    def record_success(self):
        """Record successful call"""
        self.calls.append((time.time(), True))
        self._cleanup_window()

        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= 5:  # Required successful calls to close
                self.state = CircuitState.CLOSED
                self.failures = 0
                self.successes = 0
                logger.info("Circuit breaker closed")

    def record_failure(self):
        """Record failed call"""
        self.calls.append((time.time(), False))
        self._cleanup_window()
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker reopened")
        elif self.state == CircuitState.CLOSED:
            failure_rate = self._calculate_failure_rate()
            if failure_rate > self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker opened (failure rate: {failure_rate:.2%})")

    def _cleanup_window(self):
        """Remove old calls outside the window"""
        current_time = time.time()
        self.calls = [
            (timestamp, success)
            for timestamp, success in self.calls
            if current_time - timestamp <= 60  # 1-minute window
        ]

    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate"""
        if not self.calls:
            return 0.0

        failures = sum(1 for _, success in self.calls if not success)
        return failures / len(self.calls)

    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == CircuitState.CLOSED:
            return False

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
                logger.info("Circuit breaker half-open")
                return False
            return True

        return False  # HALF_OPEN allows requests


class ConnectionPool(Generic[T]):
    """Generic connection pool with health checking and circuit breaking"""

    def __init__(
        self,
        factory: Callable[[], T],
        config: PoolConfig,
        health_check: Callable[[T], bool] | None = None,
    ):
        self.factory = factory
        self.config = config
        self.health_check = health_check
        self.pool: asyncio.Queue[T] = asyncio.Queue(maxsize=config.max_size)
        self.active_connections = 0
        self.circuit_breaker = CircuitBreaker()
        self._closing = False
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the connection pool"""
        for _ in range(self.config.min_size):
            try:
                conn = await self._create_connection()
                await self.pool.put(conn)
            except Exception as e:
                logger.error(f"Failed to initialize connection: {e}")

    async def _create_connection(self) -> T:
        """Create a new connection"""
        try:
            conn = await asyncio.wait_for(self.factory(), timeout=self.config.connection_timeout)
            self.active_connections += 1
            return conn
        except Exception as e:
            logger.error(f"Connection creation failed: {e}")
            raise

    async def acquire(self) -> T:
        """Acquire a connection from the pool"""
        if self.circuit_breaker.is_open():
            raise Exception("Circuit breaker is open")

        # Try to get from pool first
        try:
            conn = self.pool.get_nowait()

            # Health check if provided
            if self.health_check:
                if not await self.health_check(conn):
                    await self._close_connection(conn)
                    return await self.acquire()  # Retry with new connection

            return conn

        except asyncio.QueueEmpty:
            # Create new connection if under limit
            async with self._lock:
                if self.active_connections < self.config.max_size:
                    try:
                        conn = await self._create_connection()
                        self.circuit_breaker.record_success()
                        return conn
                    except Exception:
                        self.circuit_breaker.record_failure()
                        raise

            # Wait for available connection
            try:
                conn = await asyncio.wait_for(
                    self.pool.get(), timeout=self.config.connection_timeout
                )
                return conn
            except TimeoutError:
                raise Exception("Connection pool exhausted") from None

    async def release(self, conn: T):
        """Release connection back to pool"""
        if self._closing or self.pool.full():
            await self._close_connection(conn)
        else:
            try:
                self.pool.put_nowait(conn)
            except asyncio.QueueFull:
                await self._close_connection(conn)

    async def _close_connection(self, conn: T):
        """Close a connection"""
        try:
            if hasattr(conn, "close"):
                await conn.close()
            self.active_connections -= 1
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    async def close(self):
        """Close all connections in the pool"""
        self._closing = True

        # Close pooled connections
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                await self._close_connection(conn)
            except asyncio.QueueEmpty:
                break


class RetryableHTTPClient:
    """HTTP client with automatic retries and circuit breaking"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self.circuit_breaker = CircuitBreaker()

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=self.config.max_size,
            limit_per_host=self.config.max_size // 4,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )

        timeout = aiohttp.ClientTimeout(
            total=30, connect=self.config.connection_timeout, sock_read=10
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "AI-Chatbot-Enterprise/1.0", "X-Region": current_region.get()},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
    )
    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request with retries"""
        if self.circuit_breaker.is_open():
            raise Exception("Circuit breaker is open")

        try:
            response = await self.session.request(method, url, **kwargs)
            response.raise_for_status()
            self.circuit_breaker.record_success()
            return response
        except Exception:
            self.circuit_breaker.record_failure()
            raise


class RedisConnectionPool:
    """Redis connection pool with region awareness"""

    def __init__(self, redis_urls: dict[str, str], config: PoolConfig):
        self.pools: dict[str, aioredis.ConnectionPool] = {}
        self.config = config

        for region, url in redis_urls.items():
            self.pools[region] = aioredis.ConnectionPool.from_url(
                url,
                max_connections=config.max_size,
                min_connections=config.min_size,
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 30,  # TCP_KEEPINTVL
                    3: 5,  # TCP_KEEPCNT
                },
                health_check_interval=30,
            )

    def get_connection(self, region: str | None = None) -> aioredis.Redis:
        """Get Redis connection for specific region"""
        region = region or current_region.get()

        if region not in self.pools:
            raise ValueError(f"Unknown region: {region}")

        return aioredis.Redis(connection_pool=self.pools[region])

    async def close_all(self):
        """Close all connection pools"""
        for pool in self.pools.values():
            await pool.disconnect()


class DatabaseConnectionPool:
    """Database connection pool with read replica support"""

    def __init__(self, write_url: str, read_urls: list[str], config: PoolConfig):
        self.write_pool = None  # Initialize with your DB library
        self.read_pools = []  # Initialize read replicas
        self.config = config
        self.read_index = 0

    async def get_write_connection(self):
        """Get connection for write operations"""
        # Implementation depends on DB library (asyncpg, aiomysql, etc.)
        pass

    async def get_read_connection(self):
        """Get connection for read operations with load balancing"""
        # Round-robin between read replicas
        self.read_index = (self.read_index + 1) % len(self.read_pools)
        return self.read_pools[self.read_index]
