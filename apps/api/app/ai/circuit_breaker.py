import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(Enum):
    CLOSED = "closed"       # Normal — allow calls
    OPEN = "open"           # Blocking — don't call
    HALF_OPEN = "half_open"  # Testing — allow 1 call to check recovery


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation. Calls pass through.
    - OPEN: Provider is failing. Calls are blocked immediately.
    - HALF_OPEN: Testing recovery. One call is allowed through.

    Transitions:
    - CLOSED → OPEN: failure_count reaches threshold
    - OPEN → HALF_OPEN: recovery_timeout seconds have elapsed
    - HALF_OPEN → CLOSED: success_count reaches success_threshold
    - HALF_OPEN → OPEN: any failure
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        # Serializes state transitions across concurrent coroutines.
        # Prevents duplicate state transition log messages and TOCTOU races.
        self._transition_lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                logger.info("Circuit [%s]: OPEN → HALF_OPEN (testing recovery)", self.name)
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def is_available(self) -> bool:
        return self.state != CircuitState.OPEN

    async def record_success(self) -> None:
        self._failure_count = 0
        # Acquire lock before checking/transitioning HALF_OPEN → CLOSED.
        # This prevents two concurrent coroutines from both transitioning and
        # emitting duplicate log messages.
        async with self._transition_lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info("Circuit [%s]: HALF_OPEN → CLOSED ✅", self.name)
                    self._state = CircuitState.CLOSED
                    self._success_count = 0

    async def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        # Lock prevents simultaneous HALF_OPEN → OPEN transitions
        # from two concurrent failure callbacks.
        async with self._transition_lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.warning("Circuit [%s]: HALF_OPEN → OPEN 🔴 (failure during recovery test)", self.name)
                self._state = CircuitState.OPEN
                self._success_count = 0
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    "Circuit [%s]: → OPEN 🔴 (failures=%d, will retry in %ds)",
                    self.name,
                    self._failure_count,
                    self.recovery_timeout,
                )
                self._state = CircuitState.OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if not self.is_available():
            raise RuntimeError(
                f"Circuit [{self.name}] is OPEN. "
                f"AI provider temporarily unavailable, please try again in ~{self.recovery_timeout}s."
            )
        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure()
            raise


# Singleton instances — one circuit per provider
groq_circuit = CircuitBreaker(name="groq", failure_threshold=5, recovery_timeout=60)
gemini_circuit = CircuitBreaker(name="gemini", failure_threshold=5, recovery_timeout=60)
