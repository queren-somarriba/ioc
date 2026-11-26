from datetime import datetime
import os
from nicegui import app, ui
from api_client import ArchitectApiClient, ApiClientError
from state import DashboardState
from tabs.ask import render_ask_tab
from tabs.explorer import load_chunks_page, render_explorer_tab
from tabs.files import render_files_tab


client = ArchitectApiClient()
state = DashboardState()


async def refresh_index_state(record_change: bool = False) -> None:
    files_changed = False
    try:
        status_data = await client.get_status()
        files_data = await client.get_files()

        prev_chunks = state.status.get("chunks")
        new_chunks = status_data.get("chunks")
        prev_files = state.files

        state.connected = True
        state.status = status_data
        state.files = files_data
        files_changed = files_data != prev_files

        if record_change and prev_chunks is not None and new_chunks != prev_chunks:
            now = datetime.now().strftime("%H:%M:%S")
            state.push_activity(now, "index", f"Chunks update: {prev_chunks} -> {new_chunks}")
    except ApiClientError:
        state.connected = False

    render_header.refresh()
    render_overview.refresh()
    if files_changed:
        render_files_tab.refresh(client, state)


@ui.refreshable
def render_header() -> None:
    total_chunks = state.status.get("chunks", 0)
    ask_model = state.status.get("ask_model") or "n/a"
    code_model = state.status.get("code_model") or "n/a"

    with ui.header().classes("items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800"):
        with ui.row().classes("items-center gap-3"):
            ui.label("Inception-of-Context Architect").classes("text-base font-semibold")
            ui.badge(f"chunks {total_chunks}", color="slate")
            ui.badge(f"model {ask_model} / {code_model}", color="slate")
        with ui.row().classes("items-center gap-2"):
            dot_color = "text-emerald-400" if state.connected else "text-rose-400"
            label_text = "live" if state.connected else "offline"
            ui.icon("fiber_manual_record", size="xs").classes(dot_color)
            ui.label(label_text).classes("text-xs text-slate-300")


@ui.refreshable
def render_overview() -> None:
    st = state.status
    cards = [
        ("CHUNKS INDEXED", str(st.get("chunks", 0))),
        ("TARGET PROJECT", str(st.get("target_path") or "-")),
        ("CHROMA PATH", str(st.get("chroma_path") or "-")),
        ("ASK MODEL", str(st.get("ask_model") or "-")),
        ("CODE MODEL", str(st.get("code_model") or "-")),
        ("OLLAMA BACKEND", str(st.get("ollama_host") or "-"))
    ]

    with ui.column().classes("w-full gap-4 p-4"):
        with ui.card().classes("w-full bg-slate-900 border border-slate-800"):
            ui.label("STATUS").classes("text-xs font-semibold tracking-wider text-slate-400 mb-2")
            with ui.grid(columns=3).classes("w-full gap-3"):
                for title, value in cards:
                    with ui.card().classes("bg-slate-950 border border-slate-800 p-3"):
                        ui.label(title).classes("text-[10px] font-semibold text-slate-400")
                        ui.label(value).classes("text-sm font-mono text-sky-300 break-all mt-1")

        with ui.card().classes("w-full bg-slate-900 border border-slate-800"):
            ui.label("INDEXED FILES").classes("text-xs font-semibold tracking-wider text-slate-400 mb-2")
            if not state.files:
                ui.label("No indexed files.").classes("text-xs text-slate-400")
            else:
                max_c = max((int(f.get("chunks", 0)) for f in state.files), default=1) or 1
                for f in state.files:
                    path = f.get("path", "unknown")
                    count = int(f.get("chunks", 0))
                    with ui.row().classes("w-full items-center justify-between py-1"):
                        ui.label(path).classes("text-xs font-mono text-slate-200")
                        with ui.row().classes("items-center gap-2 w-48"):
                            ui.label(f"{count} chunks").classes("text-xs text-slate-400 w-16 text-right")
                            ui.linear_progress(value=min(count / max_c, 1.0)).classes("flex-1")

        with ui.card().classes("w-full bg-slate-900 border border-slate-800"):
            ui.label("LIVE ACTIVITY").classes("text-xs font-semibold tracking-wider text-slate-400 mb-2")
            if not state.activity:
                ui.label("No activity records yet.").classes("text-xs text-slate-400")
            else:
                for ev in state.activity[:15]:
                    ui.label(f"[{ev.timestamp}] ({ev.kind}) {ev.message}").classes("text-xs font-mono text-slate-300")


@ui.page("/")
async def index_page() -> None:
    ui.dark_mode(True)
    render_header()

    with ui.tabs().classes("w-full bg-slate-900 border-b border-slate-800 px-4") as tabs:
        t_overview = ui.tab("Overview")
        t_files = ui.tab("Files")
        t_explorer = ui.tab("ChromaDB Explorer")
        t_ask = ui.tab("Ask & Retrieve")
        t_patch = ui.tab("Patch Loop")

    with ui.tab_panels(tabs, value=t_overview).classes("w-full bg-slate-950 flex-1"):
        with ui.tab_panel(t_overview):
            render_overview()
        with ui.tab_panel(t_files):
            render_files_tab(client, state)
        with ui.tab_panel(t_explorer):
            render_explorer_tab(client, state)
        with ui.tab_panel(t_ask):
            render_ask_tab(client, state)
        with ui.tab_panel(t_patch):
            with ui.card().classes("m-4 bg-slate-900 border border-slate-800 p-4"):
                ui.label("PATCH LOOP").classes("text-xs font-semibold tracking-wider text-slate-400 mb-1")
                ui.label(
                    "Patchs generation and validation here when Part 3 is ok "
                ).classes("text-sm text-slate-300")

    await refresh_index_state(record_change=False)
    await load_chunks_page(
        client,
        state,
        offset=0,
        limit=int(state.chunks_page.get("limit", 20)),
        refresh_callback=lambda: render_explorer_tab.refresh(client, state),
    )

    ui.timer(3.0, lambda: refresh_index_state(record_change=True))


app.on_shutdown(client.close)

if __name__ == "__main__":
    port = int(os.getenv("IOC_DASHBOARD_PORT", "8080"))
    ui.run(host="0.0.0.0", port=port, title="Inception-of-Context Architect", reload=False)
