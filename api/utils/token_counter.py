
import tiktoken

from api.models.chat import Message


class TokenCounter:
    def __init__(self):
        self.encoders = {
            "gpt-4": tiktoken.encoding_for_model("gpt-4"),
            "gpt-3.5-turbo": tiktoken.encoding_for_model("gpt-3.5-turbo"),
            "default": tiktoken.get_encoding("cl100k_base"),
        }

    def count_tokens(self, text: str, model: str = "gpt-4") -> int:
        """Count tokens for a given text and model"""
        encoder = self.encoders.get(model, self.encoders["default"])
        return len(encoder.encode(text))

    def count_messages_tokens(self, messages: list[Message], model: str = "gpt-4") -> int:
        """Count total tokens for a list of messages"""
        encoder = self.encoders.get(model, self.encoders["default"])

        # Token overhead per message (varies by model)
        tokens_per_message = 4 if "gpt-3.5-turbo" in model else 3
        tokens_per_name = 1

        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            num_tokens += len(encoder.encode(message.content))
            num_tokens += len(encoder.encode(message.role))

            # Add tokens for name if present in metadata
            if message.metadata and "name" in message.metadata:
                num_tokens += tokens_per_name
                num_tokens += len(encoder.encode(message.metadata["name"]))

        # Every reply is primed with assistant
        num_tokens += 3

        return num_tokens

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> dict[str, float]:
        """Estimate cost breakdown for token usage"""
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        }

        if model not in pricing:
            return {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}

        input_cost = (input_tokens / 1000) * pricing[model]["input"]
        output_cost = (output_tokens / 1000) * pricing[model]["output"]

        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(input_cost + output_cost, 6),
        }

    def get_context_window(self, model: str) -> int:
        """Get the context window size for a model"""
        context_windows = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "claude-3-opus": 200000,
            "claude-3-sonnet": 200000,
        }

        return context_windows.get(model, 4096)
