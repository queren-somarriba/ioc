from nicegui import ui
from api_client import ApiClientError, ArchitectApiClient
from state import DashboardState


async def load_chunks_page(
    client: ArchitectApiClient,
    state: DashboardState,
    offset: int,
    limit: int,
    refresh_callback,
) -> None:
    safe_offset = max(0, offset)
    try:
        state.chunks_page = await client.get_chunks(offset=safe_offset, limit=limit)
    except ApiClientError as exc:
        ui.notify(exc.message, type="negative")
    refresh_callback()


@ui.refreshable
def render_explorer_tab(client: ArchitectApiClient, state: DashboardState) -> None:
    def refresh_view() -> None:
        render_explorer_tab.refresh(client, state)

    page_data = state.chunks_page
    total = int(page_data.get("total", 0))
    offset = int(page_data.get("offset", 0))
    limit = int(page_data.get("limit", 20))
    items = page_data.get("items", [])

    start_idx = min(offset + 1, total) if total > 0 else 0
    end_idx = min(offset + len(items), total)

    with ui.column().classes("w-full gap-4 p-4"):
        with ui.card().classes("w-full bg-slate-900 border border-slate-800 p-4"):
            with ui.row().classes("w-full items-center justify-between mb-3"):
                ui.label("CHROMADB EXPLORER").classes(
                    "text-xs font-semibold tracking-wider text-slate-400"
                )
                ui.label(f"Affichage {start_idx}-{end_idx} sur {total} chunks").classes(
                    "text-xs font-mono text-slate-300"
                )

            with ui.row().classes("w-full items-center justify-between mb-4"):
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Previous",
                        on_click=lambda: load_chunks_page(
                            client, state, offset - limit, limit, refresh_view
                        ),
                    ).props("outline dense").set_enabled(offset > 0)

                    ui.button(
                        "Next",
                        on_click=lambda: load_chunks_page(
                            client, state, offset + limit, limit, refresh_view
                        ),
                    ).props("outline dense").set_enabled(offset + limit < total)

                ui.button(
                    "Refresh",
                    icon="refresh",
                    on_click=lambda: load_chunks_page(client, state, offset, limit, refresh_view),
                ).props("flat dense")

            if not items:
                ui.label("No chunk to display.").classes("text-xs text-slate-400")
            else:
                for item in items:
                    chunk_id = item.get("id", "")
                    path = item.get("path", "")
                    kind = item.get("kind", "")
                    name = item.get("name", "")
                    start_line = item.get("start_line", "?")
                    end_line = item.get("end_line", "?")
                    doc = item.get("document", "")

                    with ui.expansion(
                        f"{chunk_id}  —  {path}:{start_line}-{end_line} ({kind} {name})".strip(),
                        icon="data_object",
                    ).classes("w-full bg-slate-950 border border-slate-800 rounded mb-2 text-xs font-mono"):
                        ui.code(doc, language="python").classes("w-full text-xs")