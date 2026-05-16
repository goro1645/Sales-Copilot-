from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.sales_copilot_web_utils import (
    apply_stream_event_to_progress_state,
    append_stream_log_line,
    build_progress_panel_html,
    build_card_html,
    build_dashboard_cards,
    build_stream_api_payload,
    build_summary_html,
    clear_run_result_state,
    default_stream_progress_state,
    normalize_context_rows,
    normalize_task_rows,
    parse_sse_event_block,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "sales_copilot" / "sales_copilot.db"

DEFAULT_CUSTOMER_PROFILE = """# Acme Robotics
Acme Robotics is a mid-market manufacturing company exploring a private deployment of the sales copilot workflow.
The team cares about security review, procurement timing, and a reliable follow-up process.
"""

DEFAULT_MEETING_NOTE = """CTO joined the discovery call and asked for a proposal covering private deployment.
They want a follow-up plan by Friday, asked about budget impact, and want the implementation steps broken down for the security team.
"""


def _apply_page_style() -> None:
    """给页面加一点企业工作台的质感，避免看起来像普通聊天框。"""

    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

            :root {
                --bg-1: #f5f7fb;
                --bg-2: #edf2f8;
                --panel: rgba(255, 255, 255, 0.96);
                --panel-strong: rgba(248, 251, 255, 0.98);
                --border: #d7e3f1;
                --ink: #17324d;
                --muted: #58718b;
                --accent: #2f7cf6;
                --accent-soft: #e8f1ff;
                --success: #1f9d68;
                --warning: #d88b16;
                --error: #c8485f;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(47, 124, 246, 0.10), transparent 26%),
                    radial-gradient(circle at 85% 10%, rgba(31, 157, 104, 0.08), transparent 28%),
                    linear-gradient(180deg, var(--bg-1) 0%, var(--bg-2) 100%);
            }

            html, body, [class*="css"] {
                font-family: "Space Grotesk", sans-serif;
                color: var(--ink);
            }

            .main .block-container {
                max-width: 1500px;
                padding-top: 2rem;
                padding-bottom: 2.5rem;
            }

            .hero-shell, .panel-shell, .tab-shell {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 24px;
                box-shadow: 0 18px 40px rgba(28, 55, 90, 0.08);
            }

            .hero-shell {
                padding: 1.2rem 1.4rem;
                margin-bottom: 1rem;
            }

            .hero-kicker {
                display: inline-block;
                padding: 0.28rem 0.7rem;
                border-radius: 999px;
                background: var(--accent-soft);
                color: var(--accent);
                font-weight: 700;
                font-size: 0.8rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .hero-title {
                margin-top: 0.75rem;
                font-size: 2.4rem;
                line-height: 1.08;
                font-weight: 700;
            }

            .hero-copy {
                color: var(--muted);
                margin-top: 0.35rem;
                line-height: 1.55;
            }

            .section-title {
                font-size: 1rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                color: var(--muted);
                margin-bottom: 0.8rem;
            }

            .card-shell {
                background: var(--panel-strong);
                border: 1px solid var(--border);
                border-radius: 24px;
                box-shadow: 0 12px 28px rgba(28, 55, 90, 0.08);
                padding: 0.9rem 1rem;
                min-height: 96px;
            }

            .card-label {
                color: var(--muted);
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.4rem;
            }

            .card-value {
                font-size: 1.35rem;
                font-weight: 700;
                line-height: 1.2;
                word-break: break-word;
            }

            .card-note {
                margin-top: 0.35rem;
                color: var(--muted);
                font-size: 0.82rem;
                line-height: 1.35;
            }

            .subtle-copy {
                color: var(--muted);
                font-size: 0.9rem;
                line-height: 1.5;
            }

            div[data-testid="stTextArea"] textarea,
            div[data-testid="stTextInput"] input {
                background: #ffffff;
                color: var(--ink);
                border: 1px solid var(--border);
                border-radius: 16px;
            }

            div[data-testid="stCodeBlock"] {
                background: #f7f9fc !important;
                border: 1px solid var(--border);
                border-radius: 18px;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.55rem;
            }

            .stTabs [data-baseweb="tab"] {
                background: #f3f7fc;
                border-radius: 999px;
                padding: 0.55rem 1rem;
                color: var(--muted);
            }

            .stTabs [aria-selected="true"] {
                background: var(--accent-soft);
                color: var(--ink);
            }

            .progress-shell {
                background: #ffffff;
                border: 1px solid var(--border);
                border-radius: 20px;
                padding: 1rem 1rem 0.9rem 1rem;
            }

            .progress-status-row {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                margin-bottom: 0.9rem;
                flex-wrap: wrap;
            }

            .progress-status-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                padding: 0.28rem 0.72rem;
                font-size: 0.8rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
            }

            .status-idle {
                background: #eef3f8;
                color: var(--muted);
            }

            .status-running {
                background: var(--accent-soft);
                color: var(--accent);
            }

            .status-complete {
                background: #eaf8f0;
                color: var(--success);
            }

            .status-failed {
                background: #fdecef;
                color: var(--error);
            }

            .progress-headline {
                font-size: 1.1rem;
                font-weight: 700;
                color: var(--ink);
            }

            .progress-steps {
                display: flex;
                gap: 0.55rem;
                flex-wrap: wrap;
                margin-bottom: 0.9rem;
            }

            .progress-step {
                border-radius: 999px;
                padding: 0.38rem 0.72rem;
                background: #f3f7fc;
                border: 1px solid var(--border);
                color: var(--muted);
                font-size: 0.82rem;
                font-weight: 600;
            }

            .progress-step.is-current {
                background: var(--accent-soft);
                border-color: #b9d4ff;
                color: var(--accent);
            }

            .progress-step.is-complete {
                background: #eaf8f0;
                border-color: #cdebd9;
                color: var(--success);
            }

            .progress-detail {
                color: var(--muted);
                line-height: 1.5;
                font-size: 0.95rem;
            }

            .progress-error {
                color: var(--error);
                line-height: 1.5;
                font-size: 0.95rem;
                font-weight: 600;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_session_defaults() -> None:
    st.session_state.setdefault("customer_profile_text", DEFAULT_CUSTOMER_PROFILE)
    st.session_state.setdefault("meeting_note_text", DEFAULT_MEETING_NOTE)
    st.session_state.setdefault("stream_api_base_url", "http://127.0.0.1:8011")
    st.session_state.setdefault("api_base_url", "https://api.deepseek.com")
    st.session_state.setdefault("api_key", os.getenv("DEEPSEEK_API_KEY", ""))
    st.session_state.setdefault("api_model", "deepseek-chat")
    st.session_state.setdefault("execution_mode", "direct")
    st.session_state.setdefault("database_path", str(DEFAULT_DATABASE_PATH))
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_error", "")
    st.session_state.setdefault("last_stream_log", "")
    st.session_state.setdefault("last_stream_progress", default_stream_progress_state())


def _render_progress_panel(progress_placeholder, progress_state: dict[str, Any]) -> None:
    progress_placeholder.markdown(build_progress_panel_html(progress_state), unsafe_allow_html=True)


def _render_debug_log(debug_placeholder, log_text: str) -> None:
    with debug_placeholder.container():
        with st.expander("Debug details", expanded=False):
            if log_text.strip():
                st.code(log_text, language="text")
            else:
                st.caption("Debug events will appear here while the workflow runs.")


def _consume_streaming_workflow(
    *,
    stream_api_base_url: str,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path: str,
    execution_mode: str,
    api_key: str,
    api_base_url: str,
    api_model: str,
    progress_placeholder,
    debug_placeholder,
) -> dict[str, Any]:
    endpoint = f"{stream_api_base_url.rstrip('/')}/sales-copilot/stream"
    payload = build_stream_api_payload(
        customer_profile_text=customer_profile_text,
        meeting_note_text=meeting_note_text,
        database_path=database_path,
        execution_mode=execution_mode,
        api_key=api_key,
        api_base_url=api_base_url,
        api_model=api_model,
    )

    log_text = ""
    progress_state = default_stream_progress_state()
    buffered_lines: list[str] = []
    final_result: dict[str, Any] | None = None
    stream_error: str | None = None

    with requests.post(endpoint, json=payload, stream=True, timeout=(10, 600)) as response:
        response.raise_for_status()

        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line or ""
            if line == "":
                if not buffered_lines:
                    continue
                event = parse_sse_event_block("\n".join(buffered_lines))
                buffered_lines.clear()
                if event is None:
                    continue
                progress_state = apply_stream_event_to_progress_state(progress_state, event)
                log_text = append_stream_log_line(log_text, event)
                st.session_state["last_stream_log"] = log_text
                st.session_state["last_stream_progress"] = progress_state
                _render_progress_panel(progress_placeholder, progress_state)
                _render_debug_log(debug_placeholder, log_text)
                if event.get("type") == "workflow_finished":
                    final_result = event.get("result") or {}
                elif event.get("type") == "error":
                    stream_error = str(event.get("message") or "Workflow stream failed.")
                continue
            buffered_lines.append(line)

    if buffered_lines:
        event = parse_sse_event_block("\n".join(buffered_lines))
        if event is not None:
            progress_state = apply_stream_event_to_progress_state(progress_state, event)
            log_text = append_stream_log_line(log_text, event)
            st.session_state["last_stream_log"] = log_text
            st.session_state["last_stream_progress"] = progress_state
            _render_progress_panel(progress_placeholder, progress_state)
            _render_debug_log(debug_placeholder, log_text)
            if event.get("type") == "workflow_finished":
                final_result = event.get("result") or {}
            elif event.get("type") == "error":
                stream_error = str(event.get("message") or "Workflow stream failed.")

    if final_result is None:
        if stream_error:
            raise RuntimeError(stream_error)
        raise RuntimeError("Workflow stream ended without a final result.")

    return final_result


def _render_dashboard(result: dict) -> None:
    cards = build_dashboard_cards(result)
    st.markdown('<div class="panel-shell" style="padding: 1rem 1rem 0.9rem 1rem;">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Lead Dashboard</div>', unsafe_allow_html=True)

    labels = list(cards.keys())
    values = list(cards.values())
    for start in range(0, len(labels), 4):
        row_cols = st.columns(min(4, len(labels) - start), gap="small")
        for offset, col in enumerate(row_cols):
            index = start + offset
            with col:
                note = "Dashboard summary" if labels[index] == "Account" else "Workspace metric"
                st.markdown(build_card_html(labels[index], values[index], note), unsafe_allow_html=True)

    dashboard_output = result.get("dashboard_output") or {}
    summary_text = dashboard_output.get("summary") or (result.get("follow_up_plan") or {}).get("summary") or "No summary yet."
    st.markdown("#### Executive Summary", unsafe_allow_html=True)
    st.markdown(build_summary_html(summary_text), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_crm_and_tasks(result: dict) -> None:
    st.markdown('<div class="panel-shell" style="padding: 1rem 1rem 0.9rem 1rem;">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">CRM / Tasks</div>', unsafe_allow_html=True)

    crm_preview = {
        "account_id": result.get("account_id"),
        "meeting_id": result.get("meeting_id"),
        "crm_update_ids": result.get("crm_update_ids", []),
        "opportunity_stage": result.get("opportunity_stage"),
        "priority": result.get("lead_priority"),
    }
    st.markdown("**CRM Write-Back Preview**")
    st.json(crm_preview, expanded=False)

    st.markdown("**Tasks**")
    task_rows = normalize_task_rows(result)
    if task_rows:
        st.dataframe(task_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No tasks yet. Run the copilot to generate follow-up work.")

    st.markdown("</div>", unsafe_allow_html=True)


def _render_bottom_tabs(result: dict) -> None:
    retrieved_rows = normalize_context_rows(result)
    memory = result.get("account_memory") or {}
    workflow_log = result.get("workflow_log") or []

    retrieved_tab, memory_tab, workflow_tab = st.tabs(["Retrieved Context", "Account Memory", "Workflow Log"])

    with retrieved_tab:
        if retrieved_rows:
            st.dataframe(retrieved_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Retrieved context will appear here after the first run.")

    with memory_tab:
        st.json(memory, expanded=False)

    with workflow_tab:
        if workflow_log:
            st.code("\n".join(str(item) for item in workflow_log), language="text")
        else:
            st.info("Workflow log will appear here after a run completes.")


def main() -> None:
    st.set_page_config(page_title="Sales Copilot Workbench", page_icon="briefcase", layout="wide")
    _apply_page_style()
    _ensure_session_defaults()

    st.markdown(
        """
        <div class="hero-shell">
            <span class="hero-kicker">Sales Copilot</span>
            <div class="hero-title">Enterprise Lead Workbench</div>
            <div class="hero-copy">
                Load customer context, review the lead dashboard, inspect CRM write-back work, and keep
                the full workflow trace visible in one place.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Runtime")
        stream_api_base_url = st.text_input("Streaming API Base URL", key="stream_api_base_url")
        api_base_url = st.text_input("DeepSeek Base URL", key="api_base_url")
        api_key = st.text_input("DeepSeek API Key", key="api_key", type="password")
        api_model = st.text_input("Model", key="api_model")
        execution_mode = st.selectbox("Execution Mode", ("direct", "mcp"), key="execution_mode")
        database_path = st.text_input("SQLite Path", key="database_path")
        st.caption("Start the streaming API first, then run the workflow from this page.")

    left, center, right = st.columns([1.08, 1.42, 1.08], gap="large")

    with left:
        st.markdown('<div class="panel-shell" style="padding: 1rem 1rem 0.9rem 1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Inputs</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subtle-copy">Customer profile sets the background. Meeting notes carry the facts that drive the workflow.</div>',
            unsafe_allow_html=True,
        )

        action_left, action_right = st.columns(2, gap="small")
        with action_left:
            if st.button("Load sample profile", use_container_width=True):
                st.session_state["customer_profile_text"] = DEFAULT_CUSTOMER_PROFILE
        with action_right:
            if st.button("Load sample notes", use_container_width=True):
                st.session_state["meeting_note_text"] = DEFAULT_MEETING_NOTE

        customer_profile_text = st.text_area("Customer Profile", key="customer_profile_text", height=280)
        meeting_note_text = st.text_area("Meeting Notes", key="meeting_note_text", height=280)

        run_pressed = st.button("Run Sales Copilot", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with center:
        st.markdown('<div class="panel-shell" style="padding: 1rem 1rem 0.9rem 1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Workflow Progress</div>', unsafe_allow_html=True)
        progress_placeholder = st.empty()
        _render_progress_panel(progress_placeholder, st.session_state.get("last_stream_progress", default_stream_progress_state()))
        debug_placeholder = st.empty()
        _render_debug_log(debug_placeholder, st.session_state.get("last_stream_log", ""))
        st.markdown("</div>", unsafe_allow_html=True)

    if run_pressed:
        st.session_state["last_stream_log"] = ""
        st.session_state["last_stream_progress"] = default_stream_progress_state()
        _render_progress_panel(progress_placeholder, st.session_state["last_stream_progress"])
        _render_debug_log(debug_placeholder, "")
        if not api_key.strip():
            clear_run_result_state(st.session_state, "Please provide a DeepSeek API key before running the workflow.")
        elif not stream_api_base_url.strip():
            clear_run_result_state(st.session_state, "Please provide the streaming API base URL before running the workflow.")
        else:
            try:
                st.session_state["last_error"] = ""
                st.session_state["last_result"] = _consume_streaming_workflow(
                    stream_api_base_url=stream_api_base_url,
                    customer_profile_text=customer_profile_text,
                    meeting_note_text=meeting_note_text,
                    database_path=database_path,
                    execution_mode=execution_mode,
                    api_key=api_key,
                    api_base_url=api_base_url,
                    api_model=api_model,
                    progress_placeholder=progress_placeholder,
                    debug_placeholder=debug_placeholder,
                )
            except Exception as exc:  # pragma: no cover - UI side error surfacing
                failure_state = apply_stream_event_to_progress_state(
                    st.session_state.get("last_stream_progress", default_stream_progress_state()),
                    {"type": "error", "node": "sales_copilot", "message": str(exc)},
                )
                st.session_state["last_stream_progress"] = failure_state
                _render_progress_panel(progress_placeholder, failure_state)
                clear_run_result_state(st.session_state, f"Run failed: {exc}")

    result = st.session_state.get("last_result") or {}

    with center:
        _render_dashboard(result)

    with right:
        _render_crm_and_tasks(result)

    if st.session_state.get("last_error"):
        st.error(st.session_state["last_error"])

    st.markdown('<div class="tab-shell" style="margin-top: 1rem; padding: 1rem;">', unsafe_allow_html=True)
    _render_bottom_tabs(result)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
