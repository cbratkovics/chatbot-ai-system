"""In-process demo guardrails: per-IP rate limits, token caps, daily budget.

Why: the demo runs on a public URL with a real API key behind it. These limits bound
the worst-case monthly bill without any database. State lives in the worker process
and resets on redeploy, which is acceptable for a demo and documented as such.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional


class GuardrailError(Exception):
    """Raised when a request exceeds a demo limit."""

    status_code = 429

    def __init__(self, code: str, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


@dataclass
class GuardrailConfig:
    enabled: bool = True
    per_minute: int = 10
    per_day: int = 40
    max_tokens: int = 400
    max_history_messages: int = 8
    daily_token_budget: int = 150_000


class DemoGuard:
    """Sliding-window limiter plus a shared daily token budget."""

    _MAX_TRACKED_IPS = 10_000

    def __init__(self, config: GuardrailConfig, clock: Callable[[], float] = time.time) -> None:
        self.config = config
        self._clock = clock
        self._minute: Dict[str, Deque[float]] = defaultdict(deque)
        self._day: Dict[str, Deque[float]] = defaultdict(deque)
        self._tokens_used = 0
        self._budget_day = self._day_key()

    # -- helpers -----------------------------------------------------------
    def _day_key(self) -> int:
        return int(self._clock() // 86_400)

    def _roll_budget(self) -> None:
        today = self._day_key()
        if today != self._budget_day:
            self._budget_day = today
            self._tokens_used = 0

    @staticmethod
    def _prune(window: Deque[float], cutoff: float) -> None:
        while window and window[0] <= cutoff:
            window.popleft()

    def _seconds_to_midnight(self) -> int:
        now = self._clock()
        return max(1, int(86_400 - (now % 86_400)))

    # -- public API --------------------------------------------------------
    def check(self, client_ip: str) -> None:
        """Raise GuardrailError if this request must be refused."""
        if not self.config.enabled:
            return
        now = self._clock()
        self._roll_budget()

        if self._tokens_used >= self.config.daily_token_budget:
            raise GuardrailError(
                "demo_budget_exhausted",
                "The demo's daily token budget is used up. Please try again tomorrow.",
                self._seconds_to_midnight(),
            )

        minute = self._minute[client_ip]
        self._prune(minute, now - 60)
        if len(minute) >= self.config.per_minute:
            raise GuardrailError(
                "rate_limited",
                f"Demo limit: {self.config.per_minute} requests per minute per IP.",
                max(1, int(60 - (now - minute[0]))),
            )

        day = self._day[client_ip]
        self._prune(day, now - 86_400)
        if len(day) >= self.config.per_day:
            raise GuardrailError(
                "daily_limit_reached",
                f"Demo limit: {self.config.per_day} requests per day per IP. Try again tomorrow.",
                max(1, int(86_400 - (now - day[0]))),
            )

        minute.append(now)
        day.append(now)
        self._trim_ip_tables(now)

    def _trim_ip_tables(self, now: float) -> None:
        if len(self._day) <= self._MAX_TRACKED_IPS:
            return
        for ip in list(self._day):
            if not self._day[ip] or self._day[ip][-1] < now - 86_400:
                self._day.pop(ip, None)
                self._minute.pop(ip, None)

    def clamp_max_tokens(self, requested: Optional[int]) -> int:
        if not self.config.enabled:
            return requested or self.config.max_tokens
        if requested is None:
            return self.config.max_tokens
        return min(requested, self.config.max_tokens)

    def trim_history(self, messages: List[Any]) -> List[Any]:
        """Keep system messages and the last N non-system messages."""
        if not self.config.enabled:
            return messages
        system = [m for m in messages if getattr(m, "role", None) == "system"]
        rest = [m for m in messages if getattr(m, "role", None) != "system"]
        return system + rest[-self.config.max_history_messages :]

    def record_usage(self, tokens: int) -> None:
        self._roll_budget()
        self._tokens_used += max(0, int(tokens or 0))

    def snapshot(self) -> Dict[str, Any]:
        self._roll_budget()
        return {
            "enabled": self.config.enabled,
            "per_minute": self.config.per_minute,
            "per_day": self.config.per_day,
            "max_tokens": self.config.max_tokens,
            "max_history_messages": self.config.max_history_messages,
            "daily_token_budget": self.config.daily_token_budget,
            "tokens_used_today": self._tokens_used,
        }


def client_ip_from_headers(forwarded_for: Optional[str], fallback: Optional[str]) -> str:
    """First hop of X-Forwarded-For (Render sets it), else the socket peer."""
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return fallback or "unknown"
