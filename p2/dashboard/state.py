from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActivityEvent:
    timestamp: str
    kind: str
    message: str


@dataclass
class DashboardState:
    connected: bool = False
    status: dict[str, Any] = field(default_factory=dict)
    files: list[dict[str, Any]] = field(default_factory=list)
    selected_file: str | None = None
    file_detail: dict[str, Any] | None = None
    chunks_page: dict[str, Any] = field(
        default_factory=lambda: {"items": [], "total": 0, "offset": 0, "limit": 20}
    )
    activity: list[ActivityEvent] = field(defautl_factory=list)
    last_answer: str | None = None
    last_mode: str | None = None
    last_sources: list[dict[str, Any]] = field(default_factory=list)

    def push_activity(self, timestamp: str, kind: str, message: str, max_items: int = 50) -> None:
        self.activity.insert(0, ActivityEvent(timestamp=timestamp, kind=kind, message=message))
        if len(self.activity) > max_items:
            del self.activity[max_items:]

    def set_qa_result(self, payload: dict[str, Any], default_mode: str = "rag") -> None:
        self.last_answer = payload.get("answer", "")
        self.last_mode = payload.get("mode", default_mode)
        raw_sources = payload.get("sources")
        if raw_sources is None:
            raw_sources = payload.get("source") or []
        self.last_sources = list(raw_sources)
