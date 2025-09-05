"""
Streaming mixin for AI providers to support real-time response streaming.
"""

import asyncio
import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from asyncio import Task

from .base import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """Represents a single chunk in a streaming response."""

    content: str
    index: int
    model: str
    finish_reason: Optional[str] = None
    tokens_per_second: Optional[float] = None
    is_final: bool = False
    usage: Optional[Dict[str, int]] = None


class StreamingMixin:
    """Mixin class to add streaming capabilities to providers."""

    def __init__(self, chunk_size: int = 10):
        """
        Initialize streaming mixin.

        Args:
            chunk_size: Default chunk size in tokens
        """
        self.chunk_size = chunk_size
        self.streaming_stats = {
            "total_streams": 0,
            "total_chunks": 0,
            "total_tokens": 0,
            "avg_tokens_per_second": 0.0,
        }

    @abstractmethod
    def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion response.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamChunk: Response chunks as they arrive
        """
        pass

    async def _process_stream_chunk(
        self, chunk_data: Any, index: int, model: str, start_time: float, total_tokens: int
    ) -> StreamChunk:
        """
        Process a raw stream chunk into StreamChunk object.

        Args:
            chunk_data: Raw chunk data from provider
            index: Chunk index
            model: Model identifier
            start_time: Stream start time
            total_tokens: Total tokens so far

        Returns:
            StreamChunk: Processed chunk
        """
        # Calculate tokens per second
        elapsed = time.time() - start_time
        tokens_per_second = total_tokens / elapsed if elapsed > 0 else 0

        return StreamChunk(
            content=chunk_data, index=index, model=model, tokens_per_second=tokens_per_second
        )

    def _update_streaming_stats(self, chunks: int, tokens: int, duration: float):
        """
        Update streaming statistics.

        Args:
            chunks: Number of chunks in stream
            tokens: Total tokens in stream
            duration: Stream duration in seconds
        """
        self.streaming_stats["total_streams"] += 1
        self.streaming_stats["total_chunks"] += chunks
        self.streaming_stats["total_tokens"] += tokens

        # Update average tokens per second
        if duration > 0:
            tokens_per_second = tokens / duration
            current_avg = self.streaming_stats["avg_tokens_per_second"]
            total_streams = self.streaming_stats["total_streams"]

            # Weighted average
            self.streaming_stats["avg_tokens_per_second"] = (
                current_avg * (total_streams - 1) + tokens_per_second
            ) / total_streams

    async def handle_backpressure(self, buffer_size: int = 100, wait_time: float = 0.1):
        """
        Handle backpressure in streaming.

        Args:
            buffer_size: Maximum buffer size before applying backpressure
            wait_time: Time to wait when buffer is full
        """
        # This is a placeholder for backpressure handling
        # Actual implementation would depend on the specific use case
        await asyncio.sleep(wait_time)

    async def buffer_stream(
        self, stream: AsyncIterator[StreamChunk], buffer_size: int = 10
    ) -> AsyncIterator[List[StreamChunk]]:
        """
        Buffer stream chunks for batch processing.

        Args:
            stream: Stream of chunks
            buffer_size: Number of chunks to buffer

        Yields:
            List[StreamChunk]: Batches of buffered chunks
        """
        buffer = []

        async for chunk in stream:
            buffer.append(chunk)

            if len(buffer) >= buffer_size:
                yield buffer
                buffer = []

        # Yield remaining chunks
        if buffer:
            yield buffer

    async def merge_streams(
        self, *streams: AsyncIterator[StreamChunk]
    ) -> AsyncIterator[StreamChunk]:
        """
        Merge multiple streams into one.

        Args:
            *streams: Multiple chunk streams

        Yields:
            StreamChunk: Merged stream chunks
        """
        # Use asyncio.Queue for merging
        queue: asyncio.Queue[Tuple[int, Optional[StreamChunk]]] = asyncio.Queue()
        
        # Create tasks for all streams - we'll handle them differently
        # since we can't directly create tasks from async iterators
        async def stream_wrapper(stream: AsyncIterator[StreamChunk], stream_id: int) -> None:
            async for chunk in stream:
                await queue.put((stream_id, chunk))
            await queue.put((stream_id, None))  # Sentinel
            
        tasks: List[Task[None]] = [
            asyncio.create_task(stream_wrapper(stream, i)) for i, stream in enumerate(streams)
        ]

        # Consume merged stream
        active_streams = len(streams)
        try:
            while active_streams > 0:
                stream_id, chunk = await queue.get()

                if chunk is None:
                    active_streams -= 1
                else:
                    yield chunk
        finally:
            # Clean up
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def _consume_stream(
        self, stream: AsyncIterator[StreamChunk], stream_id: int
    ) -> AsyncIterator[StreamChunk]:
        """
        Consume a stream with error handling.

        Args:
            stream: Stream to consume
            stream_id: Stream identifier

        Yields:
            StreamChunk: Stream chunks
        """
        try:
            async for chunk in stream:
                yield chunk
        except Exception as e:
            logger.error(f"Error in stream {stream_id}: {e}")
            raise


class StreamingOpenAIMixin(StreamingMixin):
    """OpenAI-specific streaming implementation."""

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion from OpenAI.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response
            **kwargs: Additional OpenAI parameters

        Yields:
            StreamChunk: Response chunks
        """
        start_time = time.time()
        chunk_index = 0
        total_tokens = 0

        try:
            # Convert messages to OpenAI format
            openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

            # Create streaming request
            request_params = {
                "model": model,
                "messages": openai_messages,
                "temperature": temperature,
                "stream": True,
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            # Add additional parameters
            request_params.update(kwargs)

            # Make streaming request
            client = getattr(self, 'client', None)
            if not client:
                raise ValueError("OpenAI client not initialized")
            stream = await client.chat.completions.create(**request_params)

            # Process stream
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_tokens += 1  # Approximate

                    yield await self._process_stream_chunk(
                        content, chunk_index, model, start_time, total_tokens
                    )

                    chunk_index += 1

                # Check for finish reason
                if chunk.choices and chunk.choices[0].finish_reason:
                    # Final chunk with usage info
                    usage = None
                    if hasattr(chunk, "usage"):
                        usage = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        }

                    yield StreamChunk(
                        content="",
                        index=chunk_index,
                        model=model,
                        finish_reason=chunk.choices[0].finish_reason,
                        is_final=True,
                        usage=usage,
                    )

            # Update statistics
            duration = time.time() - start_time
            self._update_streaming_stats(chunk_index, total_tokens, duration)

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise


class StreamingAnthropicMixin(StreamingMixin):
    """Anthropic-specific streaming implementation."""

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion from Anthropic.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response
            **kwargs: Additional Anthropic parameters

        Yields:
            StreamChunk: Response chunks
        """
        start_time = time.time()
        chunk_index = 0
        total_tokens = 0

        try:
            # Convert messages to Anthropic format
            system_message = None
            anthropic_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_message = (
                        msg.content if not system_message else f"{system_message}\n\n{msg.content}"
                    )
                else:
                    anthropic_messages.append({"role": msg.role, "content": msg.content})

            # Create streaming request
            request_params = {
                "model": model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 2048,
                "stream": True,
            }

            if system_message:
                request_params["system"] = system_message

            # Add additional parameters
            request_params.update(kwargs)

            # Make streaming request
            client = getattr(self, 'client', None)
            if not client:
                raise ValueError("Anthropic client not initialized")
            async with client.messages.stream(**request_params) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        content = event.delta.text
                        total_tokens += 1  # Approximate

                        yield await self._process_stream_chunk(
                            content, chunk_index, model, start_time, total_tokens
                        )

                        chunk_index += 1

                    elif event.type == "message_stop":
                        # Final event with usage info
                        usage = None
                        if hasattr(stream, "message") and hasattr(stream.message, "usage"):
                            usage = {
                                "prompt_tokens": stream.message.usage.input_tokens,
                                "completion_tokens": stream.message.usage.output_tokens,
                                "total_tokens": stream.message.usage.input_tokens
                                + stream.message.usage.output_tokens,
                            }

                        yield StreamChunk(
                            content="",
                            index=chunk_index,
                            model=model,
                            finish_reason="stop",
                            is_final=True,
                            usage=usage,
                        )

            # Update statistics
            duration = time.time() - start_time
            self._update_streaming_stats(chunk_index, total_tokens, duration)

        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise
