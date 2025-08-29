"""WebSocket reconnection logic with exponential backoff."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ReconnectionState(Enum):
    """Reconnection states."""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class ReconnectionConfig:
    """Configuration for reconnection logic."""

    max_attempts: int = 10
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_factor: float = 2.0
    jitter: bool = True
    timeout: float = 30.0  # connection timeout


@dataclass
class ReconnectionInfo:
    """Information about reconnection attempts."""

    session_id: str
    state: ReconnectionState
    attempts: int
    last_attempt: datetime | None
    last_success: datetime | None
    last_failure: datetime | None
    next_retry: datetime | None
    error_count: int
    errors: list


class ReconnectionManager:
    """Manages WebSocket reconnection with exponential backoff."""

    def __init__(self, config: ReconnectionConfig | None = None):
        """Initialize reconnection manager.

        Args:
            config: Reconnection configuration
        """
        self.config = config or ReconnectionConfig()
        self.sessions: dict[str, ReconnectionInfo] = {}
        self.reconnect_tasks: dict[str, asyncio.Task] = {}
        self.callbacks: dict[str, dict[str, Callable]] = {}

    def register_session(
        self,
        session_id: str,
        on_connect: Callable | None = None,
        on_disconnect: Callable | None = None,
        on_reconnect: Callable | None = None,
        on_failure: Callable | None = None,
    ):
        """Register session for reconnection management.

        Args:
            session_id: Session identifier
            on_connect: Callback on successful connection
            on_disconnect: Callback on disconnection
            on_reconnect: Callback on successful reconnection
            on_failure: Callback on reconnection failure
        """
        self.sessions[session_id] = ReconnectionInfo(
            session_id=session_id,
            state=ReconnectionState.IDLE,
            attempts=0,
            last_attempt=None,
            last_success=None,
            last_failure=None,
            next_retry=None,
            error_count=0,
            errors=[],
        )

        self.callbacks[session_id] = {
            "on_connect": on_connect,
            "on_disconnect": on_disconnect,
            "on_reconnect": on_reconnect,
            "on_failure": on_failure,
        }

        logger.info(f"Registered session {session_id} for reconnection")

    async def handle_connection(self, session_id: str, connect_func: Callable) -> bool:
        """Handle initial connection.

        Args:
            session_id: Session identifier
            connect_func: Function to establish connection

        Returns:
            True if connected successfully
        """
        if session_id not in self.sessions:
            self.register_session(session_id)

        info = self.sessions[session_id]
        info.state = ReconnectionState.CONNECTING
        info.last_attempt = datetime.utcnow()

        try:
            # Attempt connection with timeout
            await asyncio.wait_for(connect_func(), timeout=self.config.timeout)

            # Success
            info.state = ReconnectionState.CONNECTED
            info.last_success = datetime.utcnow()
            info.attempts = 0
            info.error_count = 0

            # Call callback
            if self.callbacks[session_id]["on_connect"]:
                await self.callbacks[session_id]["on_connect"](session_id)

            logger.info(f"Session {session_id} connected successfully")
            return True

        except TimeoutError:
            logger.error(f"Connection timeout for session {session_id}")
            info.state = ReconnectionState.FAILED
            info.last_failure = datetime.utcnow()
            info.errors.append("Connection timeout")
            return False

        except Exception as e:
            logger.error(f"Connection failed for session {session_id}: {e}")
            info.state = ReconnectionState.FAILED
            info.last_failure = datetime.utcnow()
            info.errors.append(str(e))
            return False

    async def handle_disconnection(
        self, session_id: str, reason: str | None = None, reconnect: bool = True
    ):
        """Handle disconnection and initiate reconnection.

        Args:
            session_id: Session identifier
            reason: Disconnection reason
            reconnect: Whether to attempt reconnection
        """
        if session_id not in self.sessions:
            return

        info = self.sessions[session_id]
        info.state = ReconnectionState.RECONNECTING if reconnect else ReconnectionState.FAILED

        # Call callback
        if self.callbacks[session_id]["on_disconnect"]:
            await self.callbacks[session_id]["on_disconnect"](session_id, reason)

        if reconnect:
            # Cancel existing reconnect task if any
            if session_id in self.reconnect_tasks:
                self.reconnect_tasks[session_id].cancel()

            # Start reconnection task
            self.reconnect_tasks[session_id] = asyncio.create_task(
                self._reconnection_loop(session_id)
            )

        logger.info(
            f"Session {session_id} disconnected (reason: {reason}), " f"reconnect: {reconnect}"
        )

    async def _reconnection_loop(self, session_id: str):
        """Reconnection loop with exponential backoff.

        Args:
            session_id: Session identifier
        """
        info = self.sessions[session_id]

        while info.attempts < self.config.max_attempts:
            # Calculate delay
            delay = self._calculate_delay(info.attempts)
            info.next_retry = datetime.utcnow() + timedelta(seconds=delay)

            logger.info(
                f"Reconnection attempt {info.attempts + 1}/{self.config.max_attempts} "
                f"for session {session_id} in {delay:.1f}s"
            )

            # Wait with jitter
            await asyncio.sleep(delay)

            # Update state
            info.attempts += 1
            info.last_attempt = datetime.utcnow()
            info.state = ReconnectionState.RECONNECTING

            try:
                # Attempt reconnection
                reconnect_func = self.callbacks[session_id].get("on_reconnect")
                if reconnect_func:
                    await asyncio.wait_for(reconnect_func(session_id), timeout=self.config.timeout)

                    # Success
                    info.state = ReconnectionState.CONNECTED
                    info.last_success = datetime.utcnow()
                    info.attempts = 0
                    info.error_count = 0
                    info.next_retry = None

                    logger.info(f"Session {session_id} reconnected successfully")
                    return
                else:
                    logger.error(f"No reconnect function for session {session_id}")
                    break

            except TimeoutError:
                logger.error(
                    f"Reconnection timeout for session {session_id} " f"(attempt {info.attempts})"
                )
                info.error_count += 1
                info.errors.append(f"Timeout at attempt {info.attempts}")

            except Exception as e:
                logger.error(
                    f"Reconnection failed for session {session_id} "
                    f"(attempt {info.attempts}): {e}"
                )
                info.error_count += 1
                info.errors.append(f"Error at attempt {info.attempts}: {str(e)}")

        # Max attempts reached
        info.state = ReconnectionState.FAILED
        info.last_failure = datetime.utcnow()

        # Call failure callback
        if self.callbacks[session_id]["on_failure"]:
            await self.callbacks[session_id]["on_failure"](
                session_id, f"Max reconnection attempts ({self.config.max_attempts}) reached"
            )

        logger.error(f"Reconnection failed for session {session_id} after {info.attempts} attempts")

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for reconnection attempt.

        Args:
            attempt: Attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(
            self.config.initial_delay * (self.config.backoff_factor**attempt),
            self.config.max_delay,
        )

        # Add jitter
        if self.config.jitter:
            import random

            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            delay += jitter

        return delay

    async def cancel_reconnection(self, session_id: str):
        """Cancel ongoing reconnection attempts.

        Args:
            session_id: Session identifier
        """
        if session_id in self.reconnect_tasks:
            self.reconnect_tasks[session_id].cancel()
            del self.reconnect_tasks[session_id]

        if session_id in self.sessions:
            self.sessions[session_id].state = ReconnectionState.IDLE
            self.sessions[session_id].next_retry = None

        logger.info(f"Cancelled reconnection for session {session_id}")

    async def force_reconnect(self, session_id: str):
        """Force immediate reconnection attempt.

        Args:
            session_id: Session identifier
        """
        if session_id not in self.sessions:
            return

        # Cancel existing task
        await self.cancel_reconnection(session_id)

        # Reset attempts
        self.sessions[session_id].attempts = 0

        # Start new reconnection
        await self.handle_disconnection(session_id, reason="Forced reconnection", reconnect=True)

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """Get reconnection information for session.

        Args:
            session_id: Session identifier

        Returns:
            Session information
        """
        if session_id not in self.sessions:
            return None

        info = self.sessions[session_id]

        return {
            "session_id": session_id,
            "state": info.state.value,
            "attempts": info.attempts,
            "max_attempts": self.config.max_attempts,
            "last_attempt": info.last_attempt.isoformat() if info.last_attempt else None,
            "last_success": info.last_success.isoformat() if info.last_success else None,
            "last_failure": info.last_failure.isoformat() if info.last_failure else None,
            "next_retry": info.next_retry.isoformat() if info.next_retry else None,
            "error_count": info.error_count,
            "recent_errors": info.errors[-5:],  # Last 5 errors
        }

    def get_stats(self) -> dict[str, Any]:
        """Get overall reconnection statistics.

        Returns:
            Statistics dictionary
        """
        total_sessions = len(self.sessions)
        states_count = {state.value: 0 for state in ReconnectionState}

        total_attempts = 0
        total_errors = 0

        for info in self.sessions.values():
            states_count[info.state.value] += 1
            total_attempts += info.attempts
            total_errors += info.error_count

        return {
            "total_sessions": total_sessions,
            "active_reconnections": len(self.reconnect_tasks),
            "states": states_count,
            "total_attempts": total_attempts,
            "total_errors": total_errors,
            "average_attempts": total_attempts / total_sessions if total_sessions > 0 else 0,
        }

    async def cleanup(self, max_age_hours: int = 24):
        """Clean up old session data.

        Args:
            max_age_hours: Maximum age in hours
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        sessions_to_remove = []

        for session_id, info in self.sessions.items():
            # Check if session is old and not active
            if info.state in [ReconnectionState.IDLE, ReconnectionState.FAILED]:
                last_activity = info.last_attempt or info.last_success or info.last_failure
                if last_activity and last_activity < cutoff_time:
                    sessions_to_remove.append(session_id)

        # Remove old sessions
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            if session_id in self.callbacks:
                del self.callbacks[session_id]

        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
