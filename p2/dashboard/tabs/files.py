from nicegui import ui
from api_client import ApiClientError, ArchitectApiClient
from state import DashboardState


async def select_file(
    client: ArchitectApiClient,
    state: DashboardState,
    path: str,
    refresh_callback,
) -> None:
    state.selected_file = path
    try:
        state.file_detail = await client.get_file(path)
    except ApiClientError as exc:
        state.file_detail = None
        ui.notify(exc.message, type="negative")
    refresh_callback()


@ui.refreshable
def render_files_tab(client: ArchitectApiClient, state: DashboardState) -> None:
    def refresh_view() -> None:
        render_files_tab.refresh(client, state)

    with ui.row().classes("w-full h-full gap-4 p-4 items-start no-wrap"):
        # Colonne gauche : liste des fichiers indexés
        with ui.card().classes("w-72 shrink-0 bg-slate-900 border border-slate-800 p-3"):
            ui.label("FILES IN TARGET").classes(
                "text-xs font-semibold tracking-wider text-slate-400 mb-2"
            )
            if not state.files:
                ui.label("No indexed file.").classes("text-xs text-slate-400")
            else:
                for f in state.files:
                    path = f.get("path", "")
                    count = f.get("chunks", 0)
                    is_selected = path == state.selected_file
                    btn_classes = (
                        "w-full justify-between text-left normal-case font-mono text-xs "
                        + ("bg-sky-900/60 text-sky-200 border border-sky-700" if is_selected else "text-slate-300")
                    )
                    with ui.button(on_click=lambda p=path: select_file(client, state, p, refresh_view)).props(
                        "flat dense"
                    ).classes(btn_classes):
                        ui.label(path).classes("truncate")
                        ui.badge(str(count), color="slate")

        # Colonne droite : contenu découpé par chunk
        with ui.card().classes("flex-1 min-w-0 bg-slate-900 border border-slate-800 p-4"):
            if not state.selected_file:
                ui.label("Select a file to inspect his chunks.").classes(
                    "text-sm text-slate-400"
                )
                return

            detail = state.file_detail or {}
            chunks = detail.get("chunks", [])
            ui.row().classes("w-full items-center justify-between mb-3").clear()
            with ui.row().classes("w-full items-center justify-between mb-3"):
                ui.label(state.selected_file).classes("text-sm font-mono font-semibold text-sky-300")
                ui.label(f"{len(chunks)} chunks").classes("text-xs text-slate-400")

            if not chunks:
                ui.label("No chunk found for this file.").classes("text-xs text-slate-400")
                return

            for idx, chunk in enumerate(chunks, start=1):
                start_line = chunk.get("start_line", "?")
                end_line = chunk.get("end_line", "?")
                kind = chunk.get("kind", "block")
                name = chunk.get("name", "")
                doc = chunk.get("document", "")

                with ui.card().classes("w-full bg-slate-950 border border-slate-800 p-3 mb-3"):
                    with ui.row().classes("w-full items-center justify-between mb-2"):
                        ui.label(f"chunk #{idx} — lines {start_line}-{end_line}").classes(
                            "text-xs font-mono text-emerald-400"
                        )
                        ui.label(f"{kind} {name}".strip()).classes("text-xs font-mono text-slate-400")
                    ui.code(doc, language="python").classes("w-full text-xs")