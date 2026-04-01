from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm.deepseek_client import DeepSeekClient
from sales_copilot.runner import run_sales_copilot
from scripts.sales_copilot_web_utils import build_dashboard_cards


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
    """简单加一点企业工作台的质感，避免页面看起来像普通聊天框。"""

    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

            :root {
                --bg-1: #08111f;
                --bg-2: #0e1d31;
                --panel: rgba(12, 24, 40, 0.82);
                --panel-strong: rgba(16, 32, 52, 0.94);
                --border: rgba(148, 188, 255, 0.16);
                --ink: #eef4ff;
                --muted: #a8bbd6;
                --accent: #69d2ff;
                --accent-2: #8af7c1;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(105, 210, 255, 0.18), transparent 25%),
                    radial-gradient(circle at 85% 10%, rgba(138, 247, 193, 0.10), transparent 28%),
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

            .hero-shell, .panel-shell, .card-shell, .tab-shell {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 24px;
                box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22);
                backdrop-filter: blur(14px);
            }

            .hero-shell {
                padding: 1.2rem 1.4rem;
                margin-bottom: 1rem;
            }

            .hero-kicker {
                display: inline-block;
                padding: 0.28rem 0.7rem;
                border-radius: 999px;
                background: rgba(105, 210, 255, 0.14);
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
                padding: 0.9rem 1rem;
                min-height: 96px;
                background: var(--panel-strong);
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
                background: rgba(255, 255, 255, 0.88);
                border-radius: 16px;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.55rem;
            }

            .stTabs [data-baseweb="tab"] {
                background: rgba(255, 255, 255, 0.06);
                border-radius: 999px;
                padding: 0.55rem 1rem;
                color: var(--muted);
            }

            .stTabs [aria-selected="true"] {
                background: rgba(105, 210, 255, 0.16);
                color: var(--ink);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_session_defaults() -> None:
    st.session_state.setdefault("customer_profile_text", DEFAULT_CUSTOMER_PROFILE)
    st.session_state.setdefault("meeting_note_text", DEFAULT_MEETING_NOTE)
    st.session_state.setdefault("api_base_url", "https://api.deepseek.com")
    st.session_state.setdefault("api_key", os.getenv("DEEPSEEK_API_KEY", ""))
    st.session_state.setdefault("api_model", "deepseek-chat")
    st.session_state.setdefault("database_path", str(DEFAULT_DATABASE_PATH))
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_error", "")


def _build_llm_client(*, api_key: str, base_url: str, model: str):
    if not api_key.strip():
        return None
    return DeepSeekClient(api_key=api_key.strip(), base_url=base_url.strip() or "https://api.deepseek.com", model=model.strip() or "deepseek-chat")


def _render_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="card-shell">
            <div class="card-label">{label}</div>
            <div class="card-value">{value}</div>
            <div class="card-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _normalize_context_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(result.get("retrieved_docs") or [], start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "Rank": index,
                "Source": item.get("source_name") or item.get("source_type") or "Context",
                "Score": item.get("score", ""),
                "Matched Terms": ", ".join(item.get("matched_terms", []) or []) or "None",
                "Snippet": str(item.get("chunk_text") or item.get("text") or item.get("description") or "")[:220],
            }
        )
    return rows


def _normalize_task_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = result.get("task_payload") or (result.get("follow_up_plan") or {}).get("tasks") or []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(tasks, start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "Rank": index,
                "Title": item.get("title", "Follow up"),
                "Priority": item.get("priority", "medium"),
                "Owner": item.get("owner", "Sales"),
                "Due": item.get("due_at", item.get("due", "")),
                "Status": item.get("status", "open"),
            }
        )
    return rows


def _render_dashboard(result: dict[str, Any]) -> None:
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
                _render_card(labels[index], values[index], note)

    dashboard_output = result.get("dashboard_output") or {}
    st.markdown("#### Executive Summary", unsafe_allow_html=True)
    st.markdown(
        f'<div class="subtle-copy">{dashboard_output.get("summary") or (result.get("follow_up_plan") or {}).get("summary") or "No summary yet."}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_crm_and_tasks(result: dict[str, Any]) -> None:
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
    task_rows = _normalize_task_rows(result)
    if task_rows:
        st.dataframe(task_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No tasks yet. Run the copilot to generate follow-up work.")

    st.markdown("</div>", unsafe_allow_html=True)


def _render_bottom_tabs(result: dict[str, Any]) -> None:
    retrieved_rows = _normalize_context_rows(result)
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
        api_base_url = st.text_input("DeepSeek Base URL", key="api_base_url")
        api_key = st.text_input("DeepSeek API Key", key="api_key", type="password")
        api_model = st.text_input("Model", key="api_model")
        database_path = st.text_input("SQLite Path", key="database_path")
        st.caption("页面可以先打开；真正运行工作流时，需要填写可用的 DeepSeek API key。")

    left, center, right = st.columns([1.08, 1.42, 1.08], gap="large")

    with left:
        st.markdown('<div class="panel-shell" style="padding: 1rem 1rem 0.9rem 1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Inputs</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle-copy">客户资料更像背景介绍，会议纪要才是主要事实来源。</div>', unsafe_allow_html=True)

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

    if run_pressed:
        llm_client = _build_llm_client(api_key=api_key, base_url=api_base_url, model=api_model)
        if llm_client is None:
            st.session_state["last_error"] = "请先在侧边栏填写 DeepSeek API key，再运行工作流。"
        else:
            try:
                st.session_state["last_error"] = ""
                st.session_state["last_result"] = run_sales_copilot(
                    customer_profile_text=customer_profile_text,
                    meeting_note_text=meeting_note_text,
                    database_path=database_path,
                    llm_client=llm_client,
                )
            except Exception as exc:  # pragma: no cover - UI side error surfacing
                st.session_state["last_error"] = f"运行失败: {exc}"

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
