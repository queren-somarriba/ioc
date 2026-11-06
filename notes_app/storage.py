"""In-memory storage for notes."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Note:
    id: int
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)


class Storage:
    """Keeps notes in memory. Easy to swap for a file or a database."""

    def __init__(self) -> None:
        self._notes: dict[int, Note] = {}
        self._next_id = 1

    def add(self, title: str, body: str = "", tags: list[str] | None = None) -> Note:
        note = Note(self._next_id, title, body, tags or [])
        self._notes[note.id] = note
        self._next_id += 1
        return note

    def get(self, note_id: int) -> Note | None:
        return self._notes.get(note_id)

    def list_all(self) -> list[Note]:
        return list(self._notes.values())

    def delete(self, note_id: int) -> bool:
        return self._notes.pop(note_id, None) is not None
