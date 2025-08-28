"""Backpressure and flow control for WebSocket streaming."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FlowControlStrategy(Enum):
    """Flow control strategies."""

    ADAPTIVE = "adaptive"  # Adjust rate based on client feedback
    FIXED = "fixed"  # Fixed rate limiting
    BUFFER = "buffer"  # Buffer with overflow handling
    THROTTLE = "throttle"  # Throttle when approaching limits


@dataclass
class FlowMetrics:
    """Metrics for flow control."""

    messages_sent: int = 0
    messages_acked: int = 0
    messages_buffered: int = 0
    bytes_sent: int = 0
    bytes_acked: int = 0
    last_ack_time: float = 0
    send_rate: float = 0  # messages per second
    ack_rate: float = 0  # acknowledgments per second
    rtt: float = 0  # round-trip time in seconds
    congestion_window: int = 10  # messages in flight


class BackpressureController:
    """Controls backpressure for WebSocket connections."""

    def __init__(
        self,
        strategy: FlowControlStrategy = FlowControlStrategy.ADAPTIVE,
        max_buffer_size: int = 1000,
        max_messages_in_flight: int = 50,
        initial_send_rate: float = 100,  # messages per second
        min_send_rate: float = 10,
        max_send_rate: float = 1000,
    ):
        """Initialize backpressure controller.

        Args:
            strategy: Flow control strategy
            max_buffer_size: Maximum buffer size
            max_messages_in_flight: Maximum unacknowledged messages
            initial_send_rate: Initial send rate
            min_send_rate: Minimum send rate
            max_send_rate: Maximum send rate
        """
        self.strategy = strategy
        self.max_buffer_size = max_buffer_size
        self.max_messages_in_flight = max_messages_in_flight
        self.initial_send_rate = initial_send_rate
        self.min_send_rate = min_send_rate
        self.max_send_rate = max_send_rate

        # Per-connection metrics
        self.connection_metrics: dict[str, FlowMetrics] = {}

        # Message buffers
        self.message_buffers: dict[str, list] = {}

        # Send rate limiters
        self.rate_limiters: dict[str, asyncio.Semaphore] = {}

    async def can_send(self, session_id: str, message_size: int = 1) -> bool:
        """Check if can send message without causing backpressure.

        Args:
            session_id: Session identifier
            message_size: Size of message in bytes

        Returns:
            True if can send
        """
        metrics = self._get_metrics(session_id)

        # Check messages in flight
        in_flight = metrics.messages_sent - metrics.messages_acked
        if in_flight >= self.max_messages_in_flight:
            return False

        # Check buffer size
        if session_id in self.message_buffers:
            if len(self.message_buffers[session_id]) >= self.max_buffer_size:
                return False

        # Strategy-specific checks
        if self.strategy == FlowControlStrategy.ADAPTIVE:
            return await self._check_adaptive(session_id, metrics)
        elif self.strategy == FlowControlStrategy.THROTTLE:
            return await self._check_throttle(session_id, metrics)

        return True

    async def send_message(self, session_id: str, message: dict[str, Any], send_func) -> bool:
        """Send message with backpressure control.

        Args:
            session_id: Session identifier
            message: Message to send
            send_func: Function to send message

        Returns:
            True if sent immediately, False if buffered
        """
        metrics = self._get_metrics(session_id)

        # Apply rate limiting
        if session_id not in self.rate_limiters:
            self.rate_limiters[session_id] = asyncio.Semaphore(int(self.initial_send_rate))

        # Check if can send
        if await self.can_send(session_id, len(str(message))):
            # Send immediately
            async with self.rate_limiters[session_id]:
                await send_func(message)

                # Update metrics
                metrics.messages_sent += 1
                metrics.bytes_sent += len(str(message))

                # Update send rate
                await self._update_send_rate(session_id, metrics)

                return True
        else:
            # Buffer message
            await self._buffer_message(session_id, message)
            return False

    async def handle_ack(self, session_id: str, ack_data: dict[str, Any]):
        """Handle acknowledgment from client.

        Args:
            session_id: Session identifier
            ack_data: Acknowledgment data
        """
        metrics = self._get_metrics(session_id)

        # Update metrics
        metrics.messages_acked = ack_data.get("message_id", metrics.messages_acked + 1)
        metrics.bytes_acked = ack_data.get("bytes_received", metrics.bytes_acked)
        metrics.last_ack_time = time.time()

        # Calculate RTT
        if "timestamp" in ack_data:
            sent_time = ack_data["timestamp"]
            metrics.rtt = time.time() - sent_time

        # Update rates
        await self._update_ack_rate(session_id, metrics)

        # Adjust congestion window (TCP-like)
        if self.strategy == FlowControlStrategy.ADAPTIVE:
            await self._adjust_congestion_window(session_id, metrics)

        # Process buffered messages
        await self._process_buffer(session_id)

    async def handle_nack(self, session_id: str, nack_data: dict[str, Any]):
        """Handle negative acknowledgment (client overload).

        Args:
            session_id: Session identifier
            nack_data: NACK data
        """
        metrics = self._get_metrics(session_id)

        # Reduce send rate
        if self.strategy == FlowControlStrategy.ADAPTIVE:
            # Multiplicative decrease (like TCP)
            metrics.congestion_window = max(1, metrics.congestion_window // 2)

            # Reduce send rate
            current_rate = self._get_send_rate(session_id)
            new_rate = max(self.min_send_rate, current_rate * 0.5)
            await self._set_send_rate(session_id, new_rate)

            logger.warning(
                f"Received NACK for session {session_id}, " f"reducing rate to {new_rate} msg/s"
            )

    async def _buffer_message(self, session_id: str, message: dict[str, Any]):
        """Buffer message for later sending.

        Args:
            session_id: Session identifier
            message: Message to buffer
        """
        if session_id not in self.message_buffers:
            self.message_buffers[session_id] = []

        buffer = self.message_buffers[session_id]

        # Apply buffer overflow strategy
        if len(buffer) >= self.max_buffer_size:
            if self.strategy == FlowControlStrategy.BUFFER:
                # Drop oldest message
                buffer.pop(0)
                logger.warning(f"Buffer overflow for session {session_id}, dropping oldest message")
            else:
                # Reject new message
                logger.error(f"Buffer full for session {session_id}, rejecting message")
                return

        buffer.append(message)

        metrics = self._get_metrics(session_id)
        metrics.messages_buffered = len(buffer)

    async def _process_buffer(self, session_id: str):
        """Process buffered messages.

        Args:
            session_id: Session identifier
        """
        if session_id not in self.message_buffers:
            return

        buffer = self.message_buffers[session_id]
        if not buffer:
            return

        # Process messages that can be sent
        messages_to_send = []
        while buffer and await self.can_send(session_id):
            messages_to_send.append(buffer.pop(0))

        # Update metrics
        if messages_to_send:
            metrics = self._get_metrics(session_id)
            metrics.messages_buffered = len(buffer)

    def _get_metrics(self, session_id: str) -> FlowMetrics:
        """Get or create metrics for session.

        Args:
            session_id: Session identifier

        Returns:
            Flow metrics
        """
        if session_id not in self.connection_metrics:
            self.connection_metrics[session_id] = FlowMetrics()
        return self.connection_metrics[session_id]

    async def _check_adaptive(self, session_id: str, metrics: FlowMetrics) -> bool:
        """Check if can send using adaptive strategy.

        Args:
            session_id: Session identifier
            metrics: Flow metrics

        Returns:
            True if can send
        """
        # Check congestion window
        in_flight = metrics.messages_sent - metrics.messages_acked
        if in_flight >= metrics.congestion_window:
            return False

        # Check RTT-based throttling
        if metrics.rtt > 1.0:  # High RTT, slow down
            await asyncio.sleep(metrics.rtt * 0.1)

        return True

    async def _check_throttle(self, session_id: str, metrics: FlowMetrics) -> bool:
        """Check if can send using throttle strategy.

        Args:
            session_id: Session identifier
            metrics: Flow metrics

        Returns:
            True if can send
        """
        # Simple throttling based on buffer usage
        buffer_usage = 0
        if session_id in self.message_buffers:
            buffer_usage = len(self.message_buffers[session_id]) / self.max_buffer_size

        if buffer_usage > 0.8:  # 80% full, aggressive throttling
            await asyncio.sleep(0.1)
        elif buffer_usage > 0.5:  # 50% full, moderate throttling
            await asyncio.sleep(0.01)

        return True

    async def _update_send_rate(self, session_id: str, metrics: FlowMetrics):
        """Update send rate based on metrics.

        Args:
            session_id: Session identifier
            metrics: Flow metrics
        """
        # Calculate current send rate
        if metrics.messages_sent > 10:
            time_elapsed = time.time() - (metrics.last_ack_time or time.time())
            if time_elapsed > 0:
                metrics.send_rate = metrics.messages_sent / time_elapsed

    async def _update_ack_rate(self, session_id: str, metrics: FlowMetrics):
        """Update acknowledgment rate.

        Args:
            session_id: Session identifier
            metrics: Flow metrics
        """
        # Calculate ack rate
        if metrics.messages_acked > 10:
            time_elapsed = time.time() - (metrics.last_ack_time or time.time())
            if time_elapsed > 0:
                metrics.ack_rate = metrics.messages_acked / time_elapsed

    async def _adjust_congestion_window(self, session_id: str, metrics: FlowMetrics):
        """Adjust congestion window based on network conditions.

        Args:
            session_id: Session identifier
            metrics: Flow metrics
        """
        # Implement TCP-like congestion control
        in_flight = metrics.messages_sent - metrics.messages_acked

        if in_flight < metrics.congestion_window:
            # No congestion, increase window (additive increase)
            metrics.congestion_window = min(
                self.max_messages_in_flight, metrics.congestion_window + 1
            )
        elif metrics.rtt > 1.0:
            # High RTT indicates congestion
            metrics.congestion_window = max(1, metrics.congestion_window - 1)

    def _get_send_rate(self, session_id: str) -> float:
        """Get current send rate.

        Args:
            session_id: Session identifier

        Returns:
            Send rate in messages per second
        """
        if session_id in self.rate_limiters:
            return self.rate_limiters[session_id]._value
        return self.initial_send_rate

    async def _set_send_rate(self, session_id: str, rate: float):
        """Set send rate.

        Args:
            session_id: Session identifier
            rate: New send rate
        """
        rate = max(self.min_send_rate, min(self.max_send_rate, rate))
        self.rate_limiters[session_id] = asyncio.Semaphore(int(rate))

    async def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get statistics for session.

        Args:
            session_id: Session identifier

        Returns:
            Session statistics
        """
        metrics = self._get_metrics(session_id)
        buffer_size = 0
        if session_id in self.message_buffers:
            buffer_size = len(self.message_buffers[session_id])

        return {
            "messages_sent": metrics.messages_sent,
            "messages_acked": metrics.messages_acked,
            "messages_in_flight": metrics.messages_sent - metrics.messages_acked,
            "messages_buffered": buffer_size,
            "bytes_sent": metrics.bytes_sent,
            "bytes_acked": metrics.bytes_acked,
            "send_rate": metrics.send_rate,
            "ack_rate": metrics.ack_rate,
            "rtt": metrics.rtt,
            "congestion_window": metrics.congestion_window,
            "buffer_usage": buffer_size / self.max_buffer_size,
        }

    async def reset_session(self, session_id: str):
        """Reset session metrics and buffers.

        Args:
            session_id: Session identifier
        """
        if session_id in self.connection_metrics:
            del self.connection_metrics[session_id]

        if session_id in self.message_buffers:
            del self.message_buffers[session_id]

        if session_id in self.rate_limiters:
            del self.rate_limiters[session_id]
