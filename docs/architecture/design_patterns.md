# Design Patterns Implementation

## Overview
This document details the design patterns implemented in the AI Chatbot System, demonstrating enterprise-grade software architecture principles.

## 1. Adapter Pattern

### Location
`api/providers/adapters/`

### Implementation Files
- `api/providers/adapters/base.py` - Abstract adapter interface
- `api/providers/adapters/openai_adapter.py` - OpenAI implementation
- `api/providers/adapters/anthropic_adapter.py` - Anthropic implementation
- `api/providers/adapters/claude_adapter.py` - Claude implementation

### Purpose
Provides a unified interface for multiple AI providers, allowing seamless switching between different LLM services without changing client code.

### Code Structure
```python
class BaseAdapter(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> Response:
        pass
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        pass

class OpenAIAdapter(BaseAdapter):
    async def generate_response(self, prompt: str, **kwargs) -> Response:
        # OpenAI-specific implementation
        return await self.client.chat.completions.create(...)

class AnthropicAdapter(BaseAdapter):
    async def generate_response(self, prompt: str, **kwargs) -> Response:
        # Anthropic-specific implementation
        return await self.client.messages.create(...)
```

### Benefits
- Provider independence
- Easy addition of new providers
- Consistent error handling
- Simplified testing through mocking

## 2. Strategy Pattern

### Location
`api/routing/model_selector.py`

### Implementation
Dynamic model selection based on query characteristics and optimization goals.

### Decision Factors
- **Token count**: Route to appropriate model based on context length
- **Task type**: Classification, generation, analysis, etc.
- **Cost optimization**: Balance between quality and cost
- **Latency requirements**: Fast vs. thorough responses
- **Load balancing**: Distribute across available providers

### Code Structure
```python
class ModelSelectionStrategy(ABC):
    @abstractmethod
    def select_model(self, query: Query) -> ModelConfig:
        pass

class CostOptimizedStrategy(ModelSelectionStrategy):
    def select_model(self, query: Query) -> ModelConfig:
        if query.token_count < 500:
            return ModelConfig(provider="openai", model="gpt-3.5-turbo")
        elif query.requires_reasoning:
            return ModelConfig(provider="anthropic", model="claude-2")
        else:
            return ModelConfig(provider="openai", model="gpt-4")

class LatencyOptimizedStrategy(ModelSelectionStrategy):
    def select_model(self, query: Query) -> ModelConfig:
        return ModelConfig(provider="openai", model="gpt-3.5-turbo")

class QualityOptimizedStrategy(ModelSelectionStrategy):
    def select_model(self, query: Query) -> ModelConfig:
        return ModelConfig(provider="openai", model="gpt-4")
```

### Strategy Selection Logic
```python
def get_strategy(optimization_goal: str) -> ModelSelectionStrategy:
    strategies = {
        "cost": CostOptimizedStrategy(),
        "latency": LatencyOptimizedStrategy(),
        "quality": QualityOptimizedStrategy()
    }
    return strategies.get(optimization_goal, CostOptimizedStrategy())
```

## 3. Chain of Responsibility Pattern

### Location
`api/middleware/pipeline.py`

### Implementation
Modular request processing pipeline with ordered middleware execution.

### Chain Components
1. **AuthMiddleware** → Validates authentication tokens
2. **RateLimitMiddleware** → Enforces rate limits
3. **GuardrailsMiddleware** → Content moderation and safety checks
4. **RoutingMiddleware** → Model selection and routing
5. **CacheMiddleware** → Cache lookup and storage
6. **TracingMiddleware** → Observability and monitoring
7. **PostProcessingMiddleware** → Response formatting and filtering

### Code Structure
```python
class Middleware(ABC):
    def __init__(self, next_handler: Optional[Middleware] = None):
        self.next_handler = next_handler
    
    async def handle(self, request: Request) -> Response:
        # Process request
        result = await self.process(request)
        
        # Pass to next handler if exists
        if self.next_handler:
            return await self.next_handler.handle(result)
        return result
    
    @abstractmethod
    async def process(self, request: Request) -> Request:
        pass

class AuthMiddleware(Middleware):
    async def process(self, request: Request) -> Request:
        if not self.validate_token(request.headers.get("Authorization")):
            raise UnauthorizedException()
        return request

class GuardrailsMiddleware(Middleware):
    async def process(self, request: Request) -> Request:
        if self.contains_harmful_content(request.body):
            raise ContentPolicyViolation()
        return request
```

### Pipeline Assembly
```python
def build_middleware_pipeline() -> Middleware:
    return AuthMiddleware(
        RateLimitMiddleware(
            GuardrailsMiddleware(
                RoutingMiddleware(
                    CacheMiddleware(
                        TracingMiddleware(
                            PostProcessingMiddleware()
                        )
                    )
                )
            )
        )
    )
```

## 4. Observer Pattern

### Location
`api/services/events/`

### Implementation
Event-driven architecture for decoupled component communication.

### Event Types
- Request received
- Cache hit/miss
- Model selected
- Response generated
- Error occurred
- Rate limit exceeded

### Code Structure
```python
class EventManager:
    def __init__(self):
        self.listeners = defaultdict(list)
    
    def subscribe(self, event_type: str, handler: Callable):
        self.listeners[event_type].append(handler)
    
    async def emit(self, event_type: str, data: Dict):
        for handler in self.listeners[event_type]:
            await handler(data)

class MetricsCollector:
    def __init__(self, event_manager: EventManager):
        event_manager.subscribe("request_received", self.on_request)
        event_manager.subscribe("cache_hit", self.on_cache_hit)
    
    async def on_request(self, data: Dict):
        self.request_count += 1
    
    async def on_cache_hit(self, data: Dict):
        self.cache_hits += 1
```

## 5. Repository Pattern

### Location
`api/repositories/`

### Implementation
Data access abstraction layer for database operations.

### Benefits
- Database independence
- Testability through mocking
- Centralized query logic
- Consistent data access patterns

### Code Structure
```python
class BaseRepository(ABC):
    @abstractmethod
    async def get(self, id: str) -> Optional[Model]:
        pass
    
    @abstractmethod
    async def create(self, data: Dict) -> Model:
        pass
    
    @abstractmethod
    async def update(self, id: str, data: Dict) -> Model:
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        pass

class ConversationRepository(BaseRepository):
    async def get(self, id: str) -> Optional[Conversation]:
        return await self.db.conversations.find_one({"_id": id})
    
    async def get_by_user(self, user_id: str) -> List[Conversation]:
        return await self.db.conversations.find({"user_id": user_id}).to_list()
```

## 6. Factory Pattern

### Location
`api/factories/`

### Implementation
Object creation abstraction for complex initialization logic.

### Use Cases
- Provider adapter creation
- Model configuration
- Cache backend initialization
- Database connection setup

### Code Structure
```python
class AdapterFactory:
    @staticmethod
    def create_adapter(provider: str, config: Dict) -> BaseAdapter:
        adapters = {
            "openai": OpenAIAdapter,
            "anthropic": AnthropicAdapter,
            "claude": ClaudeAdapter,
            "huggingface": HuggingFaceAdapter
        }
        
        adapter_class = adapters.get(provider)
        if not adapter_class:
            raise ValueError(f"Unknown provider: {provider}")
        
        return adapter_class(**config)

class CacheFactory:
    @staticmethod
    def create_cache(backend: str, config: Dict) -> BaseCache:
        if backend == "redis":
            return RedisCache(**config)
        elif backend == "memory":
            return InMemoryCache(**config)
        elif backend == "dynamodb":
            return DynamoDBCache(**config)
        else:
            raise ValueError(f"Unknown cache backend: {backend}")
```

## 7. Singleton Pattern

### Location
`api/services/config.py`

### Implementation
Global configuration management with single instance guarantee.

### Code Structure
```python
class ConfigurationManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        # Load from environment, files, etc.
        return {}
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)
```

## 8. Decorator Pattern

### Location
`api/decorators/`

### Implementation
Dynamic behavior addition to functions and methods.

### Use Cases
- Caching
- Rate limiting
- Authentication
- Logging
- Metrics collection

### Code Structure
```python
def cached(ttl: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(args)}:{hash(frozenset(kwargs.items()))}"
            
            # Try cache lookup
            cached_result = await cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache.set(cache_key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator

def rate_limited(max_calls: int = 10, period: int = 60):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get("user_id")
            if await rate_limiter.is_exceeded(user_id, max_calls, period):
                raise RateLimitExceeded()
            
            await rate_limiter.increment(user_id)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

## 9. Command Pattern

### Location
`api/commands/`

### Implementation
Encapsulation of requests as objects for queuing and undo operations.

### Code Structure
```python
class Command(ABC):
    @abstractmethod
    async def execute(self) -> Any:
        pass
    
    @abstractmethod
    async def undo(self) -> None:
        pass

class GenerateResponseCommand(Command):
    def __init__(self, prompt: str, model: str, parameters: Dict):
        self.prompt = prompt
        self.model = model
        self.parameters = parameters
        self.result = None
    
    async def execute(self) -> str:
        adapter = AdapterFactory.create_adapter(self.model)
        self.result = await adapter.generate_response(
            self.prompt, 
            **self.parameters
        )
        return self.result
    
    async def undo(self) -> None:
        # Log reversal, clean up resources, etc.
        if self.result:
            await cache.delete(self.result.cache_key)

class CommandQueue:
    def __init__(self):
        self.queue = []
        self.history = []
    
    async def add(self, command: Command):
        self.queue.append(command)
    
    async def execute_all(self):
        while self.queue:
            command = self.queue.pop(0)
            result = await command.execute()
            self.history.append(command)
```

## 10. Template Method Pattern

### Location
`api/processors/base.py`

### Implementation
Defines algorithm skeleton with customizable steps.

### Code Structure
```python
class BaseProcessor(ABC):
    async def process(self, data: Dict) -> Dict:
        # Template method defining the algorithm
        validated_data = await self.validate(data)
        preprocessed = await self.preprocess(validated_data)
        result = await self.execute(preprocessed)
        postprocessed = await self.postprocess(result)
        return await self.format_response(postprocessed)
    
    @abstractmethod
    async def validate(self, data: Dict) -> Dict:
        pass
    
    @abstractmethod
    async def preprocess(self, data: Dict) -> Dict:
        pass
    
    @abstractmethod
    async def execute(self, data: Dict) -> Dict:
        pass
    
    async def postprocess(self, data: Dict) -> Dict:
        # Default implementation
        return data
    
    async def format_response(self, data: Dict) -> Dict:
        # Default implementation
        return {"status": "success", "data": data}

class ChatProcessor(BaseProcessor):
    async def validate(self, data: Dict) -> Dict:
        if "message" not in data:
            raise ValueError("Message required")
        return data
    
    async def preprocess(self, data: Dict) -> Dict:
        # Clean and prepare message
        data["message"] = data["message"].strip()
        return data
    
    async def execute(self, data: Dict) -> Dict:
        # Process chat message
        response = await llm.generate(data["message"])
        return {"response": response}
```

## Architecture Benefits

### Maintainability
- Clear separation of concerns
- Modular component design
- Easy to locate and modify functionality

### Scalability
- Horizontal scaling through stateless design
- Efficient resource utilization
- Load distribution capabilities

### Testability
- Mockable interfaces
- Isolated component testing
- Clear dependency injection

### Flexibility
- Easy provider switching
- Configurable processing pipeline
- Extensible architecture

### Performance
- Efficient caching strategies
- Optimized request batching
- Lazy loading and initialization

## Related Documentation
- [Message Flow Diagram](./message_flow.png)
- [System Architecture](../../README.md#architecture)
- [API Documentation](../../api/README.md)