"""Entry point (NiceGUI). Run with: python main.py"""
from __future__ import annotations

from nicegui import ui

from service import NoteService

service = NoteService()
service.create("Welcome", "This is the first note.", ["demo"])


@ui.refreshable
def notes_list(term: str = "") -> None:
    notes = service.search(term) if term else service.list_all()
    if not notes:
        ui.label("No notes.")
    for note in notes:
        with ui.card().classes("w-full"):
            ui.label(note.title).classes("text-lg font-bold")
            ui.label(note.body)
            ui.label(", ".join(note.tags)).classes("text-sm text-gray-500")
            ui.button("Delete", on_click=lambda n=note: delete_note(n.id))


def parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def add_note(title, body, tags) -> None:
    try:
        service.create(title.value, body.value, parse_tags(tags.value))
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        return
    title.value = body.value = tags.value = ""
    notes_list.refresh()


def delete_note(note_id: int) -> None:
    service.remove(note_id)
    notes_list.refresh()


def build_page() -> None:
    ui.label("Notes").classes("text-2xl font-bold")
    title = ui.input("Title")
    body = ui.textarea("Body")
    tags = ui.input("Tags (comma separated)")
    ui.button("Add", on_click=lambda: add_note(title, body, tags))
    ui.input("Search", on_change=lambda e: notes_list.refresh(e.value))
    notes_list()


if __name__ in {"__main__", "__mp_main__"}:
    build_page()
    ui.run(title="Notes demo", port=8080)
