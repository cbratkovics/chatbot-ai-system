"""Simple OpenAI provider implementation."""

import os
from typing import Any, AsyncIterator, Dict, Optional

from chatbot_ai_system.schemas import ChatRequest


class SimpleOpenAIProvider:
    """OpenAI API provider."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                # OpenAI not installed, use mock
                return None
        return self._client
    
    async def complete(self, request: ChatRequest) -> Dict[str, Any]:
        """Generate completion from OpenAI."""
        client = self._get_client()
        if not client:
            return {
                "content": "OpenAI provider not available (package not installed)",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
        
        try:
            # Convert messages to the format OpenAI expects
            messages = []
            for m in request.messages:
                if isinstance(m, dict):
                    messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
                else:
                    messages.append({"role": "user", "content": str(m)})
            
            response = await client.chat.completions.create(
                model=request.model or "gpt-3.5-turbo",
                messages=messages,
                temperature=request.temperature if hasattr(request, 'temperature') else 0.7,
                max_tokens=request.max_tokens if hasattr(request, 'max_tokens') else 1000,
                stream=False,
            )
            
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }
        except Exception as e:
            return {
                "content": f"Error calling OpenAI API: {str(e)}",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
    
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream completion from OpenAI."""
        client = self._get_client()
        if not client:
            yield "OpenAI provider not available"
            return
        
        try:
            # Convert messages to the format OpenAI expects
            messages = []
            for m in request.messages:
                if isinstance(m, dict):
                    messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
                else:
                    messages.append({"role": "user", "content": str(m)})
            
            stream = await client.chat.completions.create(
                model=request.model or "gpt-3.5-turbo",
                messages=messages,
                temperature=request.temperature if hasattr(request, 'temperature') else 0.7,
                max_tokens=request.max_tokens if hasattr(request, 'max_tokens') else 1000,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error: {str(e)}"
    
    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            client = self._get_client()
            if client:
                await client.models.list()
                return True
        except Exception:
            pass
        return False