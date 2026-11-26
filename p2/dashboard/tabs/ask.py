from nicegui import ui
from api_client import ApiClientError, ArchitectApiClient
from state import DashboardState


async def run_retrieve(
    client: ArchitectApiClient,
    state: DashboardState,
    query: str,
    k: int,
    refresh_callback,
) -> None:
    cleaned = query.strip()
    if not cleaned:
        ui.notify("Saisis une question ou une intention avant de lancer Retrieve.", type="warning")
        return

    try:
        res = await client.post_context(query=cleaned, k=int(k))
        chunks = res.get("chunks", [])
        state.last_mode = "retrieve"
        state.last_answer = None
        state.last_sources = chunks
    except ApiClientError as exc:
        ui.notify(exc.message, type="negative")
    refresh_callback()


async def run_ask(
    client: ArchitectApiClient,
    state: DashboardState,
    question: str,
    k: int,
    refresh_callback,
) -> None:
    cleaned = question.strip()
    if not cleaned:
        ui.notify("Saisis une question avant d'interroger le LLM.", type="warning")
        return

    try:
        res = await client.post_ask(question=cleaned, k=int(k))
        state.set_qa_result(res, default_mode="rag")
    except ApiClientError as exc:
        ui.notify(exc.message, type="negative")
    refresh_callback()


@ui.refreshable
def render_ask_tab(client: ArchitectApiClient, state: DashboardState) -> None:
    def refresh_view() -> None:
        render_ask_tab.refresh(client, state)

    query_holder = {"text": ""}
    k_holder = {"value": 5}

    with ui.column().classes("w-full gap-4 p-4"):
        with ui.card().classes("w-full bg-slate-900 border border-slate-800 p-4"):
            ui.label("RETRIEVE / ASK").classes(
                "text-xs font-semibold tracking-wider text-slate-400 mb-2"
            )
            textarea = (
                ui.textarea(
                    placeholder="Ex: explain how NoteService.search works or is authenticate defined?",
                    value=query_holder["text"],
                )
                .classes("w-full font-mono text-xs")
                .props("rows=3 outlined")
            )
            textarea.on_value_change(lambda e: query_holder.update({"text": e.value or ""}))

            with ui.row().classes("w-full items-center gap-3 mt-3"):
                k_input = (
                    ui.number(label="k", value=k_holder["value"], min=1, max=20, step=1)
                    .classes("w-24")
                    .props("dense outlined")
                )
                k_input.on_value_change(
                    lambda e: k_holder.update({"value": int(e.value) if e.value is not None else 5})
                )

                btn_retrieve = ui.button(
                    "Retrieve",
                    on_click=lambda: _guarded_action(
                        btn_retrieve,
                        btn_ask,
                        lambda: run_retrieve(
                            client, state, query_holder["text"], k_holder["value"], refresh_view
                        ),
                    ),
                ).props("outline")

                btn_ask = ui.button(
                    "Ask LLM",
                    on_click=lambda: _guarded_action(
                        btn_ask,
                        btn_retrieve,
                        lambda: run_ask(
                            client, state, query_holder["text"], k_holder["value"], refresh_view
                        ),
                    ),
                ).props("unelevated color=primary")

        if state.last_answer is not None:
            with ui.card().classes("w-full bg-slate-900 border border-slate-800 p-4"):
                with ui.row().classes("w-full items-center justify-between mb-2"):
                    ui.label("ANSWER").classes(
                        "text-xs font-semibold tracking-wider text-sky-400"
                    )
                    if state.last_mode:
                        ui.badge(f"mode: {state.last_mode}", color="slate")
                ui.markdown(state.last_answer).classes("text-sm text-slate-100")

        if state.last_sources:
            with ui.card().classes("w-full bg-slate-900 border border-slate-800 p-4"):
                ui.label(f"SOURCES ({len(state.last_sources)})").classes(
                    "text-xs font-semibold tracking-wider text-slate-400 mb-2"
                )
                for src in state.last_sources:
                    src_id = src.get("id", f"{src.get('path', '?')}:{src.get('start_line', '?')}")
                    start_line = src.get("start_line", "?")
                    end_line = src.get("end_line", "?")
                    score = src.get("score")
                    rrf = src.get("rrf")

                    meta_bits = [f"lines {start_line}-{end_line}"]
                    if score is not None:
                        meta_bits.append(f"score {score}")
                    if rrf is not None:
                        meta_bits.append(f"rrf {rrf}")

                    header = f"{src_id}  —  {' · '.join(meta_bits)}"
                    doc = src.get("document")

                    with ui.expansion(header, icon="code").classes(
                        "w-full bg-slate-950 border border-slate-800 rounded mb-2 text-xs font-mono"
                    ):
                        if doc:
                            ui.code(doc, language="python").classes("w-full text-xs")
                        else:
                            ui.label(
                                f"Symbole : {src.get('name', '?')} ({src.get('path', '?')})"
                            ).classes("text-xs text-slate-400")


async def _guarded_action(primary_btn, secondary_btn, coro_factory) -> None:
    primary_btn.disable()
    secondary_btn.disable()
    spinner = ui.spinner("dots", size="sm")
    try:
        await coro_factory()
    finally:
        spinner.delete()
        primary_btn.enable()
        secondary_btn.enable()