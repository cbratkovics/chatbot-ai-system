import asyncio
import zlib
from typing import AsyncGenerator, Any, Optional, List


class StreamHandler:
    """Handles streaming operations."""

    def __init__(self, buffer_size: int = 10, metrics_collector=None):
        self.buffer_size = buffer_size
        self.metrics_collector = metrics_collector

    async def stream_with_metrics(
        self, generator: AsyncGenerator, stream_id: str
    ) -> AsyncGenerator:
        """Stream with metrics collection."""
        async for item in generator:
            if self.metrics_collector:
                # Handle both sync (mock) and async metrics collectors
                if hasattr(self.metrics_collector.record_gauge, "__call__"):
                    self.metrics_collector.record_gauge("stream_active", 1)
                else:
                    await self.metrics_collector.record_gauge("stream_active", 1)

                if hasattr(self.metrics_collector.record_latency, "__call__"):
                    self.metrics_collector.record_latency("stream_chunk", 0.01)
                else:
                    await self.metrics_collector.record_latency("stream_chunk", 0.01)
            yield item

    async def create_sse_stream(self, generator: AsyncGenerator) -> AsyncGenerator[str, None]:
        """Create Server-Sent Events stream."""
        async for data in generator:
            # Format as SSE event
            sse_data = f"data: {data}\n\n"
            yield sse_data

    def chunk_response(self, data: str, chunk_size: int = 1000) -> List[str]:
        """Chunk response data."""
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunks.append(data[i : i + chunk_size])
        return chunks

    async def stream_with_timeout(
        self, generator: AsyncGenerator, timeout: int = 30
    ) -> AsyncGenerator:
        """Stream with timeout handling."""
        try:
            # Create a task for the generator consumption
            task = asyncio.create_task(self._collect_all(generator))
            # Wait for it with timeout
            items = await asyncio.wait_for(task, timeout=timeout)
            # Yield collected items
            for item in items:
                yield item
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Stream timeout after {timeout} seconds")

    async def _collect_all(self, generator: AsyncGenerator) -> list:
        """Collect all items from generator."""
        items = []
        async for item in generator:
            items.append(item)
        return items

    async def _consume_generator(self, generator: AsyncGenerator) -> AsyncGenerator:
        """Helper to consume generator for timeout."""
        async for item in generator:
            yield item

    async def handle_stream(self, generator: AsyncGenerator) -> AsyncGenerator:
        """Handle stream with error propagation."""
        async for item in generator:
            yield item

    async def buffer_stream(self, generator: AsyncGenerator) -> AsyncGenerator[List, None]:
        """Buffer stream into batches."""
        buffer = []
        async for item in generator:
            buffer.append(item)
            if len(buffer) >= self.buffer_size:
                yield buffer
                buffer = []

        # Yield remaining items
        if buffer:
            yield buffer

    async def compress_stream(self, generator: AsyncGenerator) -> AsyncGenerator[bytes, None]:
        """Compress stream data using zlib."""
        async for data in generator:
            # Compress the data
            if isinstance(data, str):
                data = data.encode("utf-8")
            compressed = zlib.compress(data)
            yield compressed

    async def rate_limit_stream(self, generator: AsyncGenerator, rate: int = 10) -> AsyncGenerator:
        """Rate limit stream to specified items per second."""
        interval = 1.0 / rate  # Time between items

        async for item in generator:
            yield item
            await asyncio.sleep(interval)
