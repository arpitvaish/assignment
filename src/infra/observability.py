"""
Structured observability: event log with timestamps and context.
"""
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EventLog:
    event: str
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    level: str = "INFO"

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "timestamp": self.timestamp,
            "level": self.level,
            "context": self.context,
        }


class ObservabilityBus:
    """Collects EventLog entries and dispatches to registered handlers."""

    def __init__(self):
        self._events: List[EventLog] = []
        self._handlers: List[Callable[[EventLog], None]] = [self._default_handler]

    def add_handler(self, fn: Callable[[EventLog], None]):
        self._handlers.append(fn)

    def emit(self, event: str, context: Dict[str, Any] = None, level: str = "INFO"):
        log = EventLog(event=event, context=context or {}, level=level)
        self._events.append(log)
        for handler in self._handlers:
            try:
                handler(log)
            except Exception:
                pass

    def _default_handler(self, log: EventLog):
        lvl = getattr(logging, log.level, logging.INFO)
        logger.log(lvl, "[%s] %s", log.event, log.context)

    def events(self, event_filter: Optional[str] = None) -> List[EventLog]:
        if event_filter:
            return [e for e in self._events if e.event == event_filter]
        return list(self._events)

    def clear(self):
        self._events.clear()
