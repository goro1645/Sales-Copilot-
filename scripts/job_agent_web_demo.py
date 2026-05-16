"""Streamlit 网页演示入口。

这个文件是整个项目的“前台页面”：
- 左侧收集用户输入
- 侧边栏控制运行模式
- 下方展示 Agent 运行结果

如果你是第一次看这个项目，建议从这里开始，
先理解页面怎么收集数据，再顺着 `run_job_agent(...)` 往里读。
"""

import os
import sys
from pathlib import Path

import streamlit as st

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.runner import run_job_agent
from agent.storage import list_application_records
from scripts.job_agent_web_utils import (
    build_history_rows,
    build_runner_kwargs,
    load_sample_documents,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "job_agent"
DEFAULT_DB_PATH = DATA_DIR / "applications.db"


def apply_page_style():
    """给 Streamlit 页面注入自定义样式。

    这一大段 CSS 主要负责页面“长什么样”，不参与业务逻辑。
    读代码时如果你更想先理解 Agent 流程，可以先快速略过这里。
    """

    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

            :root {
                --bg-top: #f7f3e8;
                --bg-bottom: #dbe7e1;
                --panel: rgba(255, 252, 246, 0.78);
                --panel-strong: rgba(255, 255, 255, 0.9);
                --border: rgba(31, 55, 46, 0.12);
                --ink: #17362d;
                --muted: #4f6b61;
                --accent: #0b7a5c;
                --accent-soft: rgba(11, 122, 92, 0.12);
                --warning: #b26b2b;
                --danger: #ae4f45;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(255, 241, 214, 0.65), transparent 35%),
                    radial-gradient(circle at top right, rgba(113, 167, 142, 0.20), transparent 30%),
                    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
            }

            .main .block-container {
                max-width: 1180px;
                padding-top: 2.2rem;
                padding-bottom: 3rem;
            }

            html, body, [class*="css"]  {
                font-family: "Space Grotesk", sans-serif;
                color: var(--ink);
            }

            .hero-shell, .panel-shell, .result-shell, .metric-shell {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 24px;
                box-shadow: 0 18px 60px rgba(25, 61, 49, 0.08);
                backdrop-filter: blur(12px);
            }

            .hero-shell {
                padding: 1.6rem 1.6rem 1.3rem 1.6rem;
                margin-bottom: 1rem;
            }

            .hero-kicker {
                display: inline-block;
                padding: 0.35rem 0.7rem;
                border-radius: 999px;
                background: var(--accent-soft);
                color: var(--accent);
                font-size: 0.82rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
            }

            .hero-title {
                margin: 0.8rem 0 0.4rem 0;
                font-size: 2.45rem;
                line-height: 1.05;
                font-weight: 700;
            }

            .hero-copy {
                color: var(--muted);
                font-size: 1rem;
                line-height: 1.65;
                margin-bottom: 0.2rem;
            }

            .panel-shell, .result-shell {
                padding: 1rem 1rem 0.9rem 1rem;
            }

            .metric-shell {
                padding: 1rem 1.1rem;
                min-height: 122px;
                background: var(--panel-strong);
            }

            .metric-label {
                color: var(--muted);
                font-size: 0.82rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                margin-bottom: 0.45rem;
            }

            .metric-value {
                font-size: 2rem;
                font-weight: 700;
                line-height: 1;
                margin-bottom: 0.5rem;
            }

            .metric-note {
                color: var(--muted);
                font-size: 0.92rem;
                line-height: 1.4;
            }

            .section-title {
                font-size: 1.1rem;
                font-weight: 700;
                margin-bottom: 0.65rem;
            }

            .mono-note {
                font-family: "IBM Plex Mono", monospace;
                color: var(--muted);
                font-size: 0.82rem;
            }

            .status-chip {
                display: inline-block;
                padding: 0.3rem 0.65rem;
                border-radius: 999px;
                font-size: 0.84rem;
                font-weight: 700;
                margin-top: 0.25rem;
            }

            .status-ready_to_apply {
                background: rgba(11, 122, 92, 0.12);
                color: var(--accent);
            }

            .status-rewrite_resume {
                background: rgba(178, 107, 43, 0.12);
                color: var(--warning);
            }

            .status-reject {
                background: rgba(174, 79, 69, 0.12);
                color: var(--danger);
            }

            div[data-testid="stTextArea"] textarea,
            div[data-testid="stTextInput"] input {
                background: rgba(255,255,255,0.75);
                border-radius: 16px;
            }

            @media (max-width: 768px) {
                .hero-title {
                    font-size: 1.9rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_session_defaults():
    """给页面第一次打开时准备默认值。

    `st.session_state` 可以理解成页面运行过程中的“小内存”。
    我们把样例 JD、样例简历、默认公司和岗位名放进去，
    这样页面第一次打开就能直接体验，而不是完全空白。
    """

    samples = load_sample_documents(DATA_DIR)
    st.session_state.setdefault("job_posting_text", samples["job_posting"])
    st.session_state.setdefault("resume_text", samples["resume_text"])
    st.session_state.setdefault("company", "MiniMind Labs")
    st.session_state.setdefault("role", "LLM Application Engineer")
    st.session_state.setdefault("last_result", None)


def render_hero():
    """渲染页面顶部标题区。"""

    st.markdown(
        """
        <div class="hero-shell">
            <span class="hero-kicker">MiniMind + LangGraph</span>
            <div class="hero-title">Job Agent Control Room</div>
            <div class="hero-copy">
                Run a semi-automatic application workflow that parses a job description, scores resume fit,
                rewrites project bullets, drafts a cover letter, and stores the result for follow-up.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric(label: str, value: str, note: str):
    """渲染一个指标卡片。"""

    st.markdown(
        f"""
        <div class="metric-shell">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_settings_panel():
    """渲染侧边栏设置。

    这里控制的是“怎么运行 Agent”，例如：
    - 是否启用真实 MiniMind API
    - API 地址是什么
    - 数据库保存到哪里
    """

    with st.sidebar:
        st.markdown("### Runtime")
        use_api_generation = st.toggle(
            "Use MiniMind API generation",
            value=False,
            help="When enabled, the app calls the local OpenAI-style MiniMind API for rewriting and cover letters.",
        )
        api_base_url = st.text_input("API Base URL", value="http://127.0.0.1:8998/v1")
        api_key = st.text_input("API Key", value="minimind")
        api_model = st.text_input("API Model", value="minimind")
        database_path = st.text_input("SQLite Path", value=str(DEFAULT_DB_PATH))
        st.caption("Keep generation off if your local MiniMind API is not running yet.")

    # 统一打包成 dict 返回，能让后面的页面函数依赖更清楚。
    return {
        "use_api_generation": use_api_generation,
        "api_base_url": api_base_url,
        "api_key": api_key,
        "api_model": api_model,
        "database_path": database_path,
    }


def render_input_panel(settings: dict):
    """渲染主输入区，并在点击按钮时触发 Job Agent。"""

    # 左边是表单输入，右边是运行配置和历史记录。
    left, right = st.columns([1.6, 1], gap="large")

    with left:
        st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Application Inputs</div>', unsafe_allow_html=True)

        top_left, top_right = st.columns(2, gap="medium")
        with top_left:
            company = st.text_input("Company", key="company")
        with top_right:
            role = st.text_input("Role", key="role")

        action_left, action_right, action_spacer = st.columns([1, 1, 2])
        with action_left:
            if st.button("Load sample JD", use_container_width=True):
                # 把样例 JD 写回 session_state，文本框会自动刷新成新内容。
                st.session_state["job_posting_text"] = load_sample_documents(DATA_DIR)["job_posting"]
        with action_right:
            if st.button("Load sample resume", use_container_width=True):
                st.session_state["resume_text"] = load_sample_documents(DATA_DIR)["resume_text"]

        job_posting = st.text_area("Job Description", key="job_posting_text", height=280)
        resume_text = st.text_area("Resume", key="resume_text", height=280)

        submitted = st.button("Run Job Agent", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Run Configuration</div>', unsafe_allow_html=True)
        mode = "MiniMind API generation" if settings["use_api_generation"] else "Deterministic fallback"
        st.markdown(f"**Mode**  \n{mode}")
        st.markdown(f"**Database**  \n`{settings['database_path']}`")
        st.markdown(
            '<div class="mono-note">Tip: start with deterministic mode, then switch on API generation after your local MiniMind service is up.</div>',
            unsafe_allow_html=True,
        )

        # 每次页面渲染时，都从 SQLite 读一遍历史记录，
        # 这样你一跑完新结果，右边列表就会同步出现。
        rows = build_history_rows(list_application_records(settings["database_path"]))
        st.markdown("---")
        st.markdown('<div class="section-title">Recent Application Records</div>', unsafe_allow_html=True)
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No saved applications yet. Run the agent once to create the first record.")
        st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        # 先把页面采集到的输入整理成 runner 需要的参数结构。
        kwargs = build_runner_kwargs(
            company=company,
            role=role,
            job_posting=job_posting,
            resume_text=resume_text,
            database_path=settings["database_path"],
            use_api_generation=settings["use_api_generation"],
            api_base_url=settings["api_base_url"],
            api_key=settings["api_key"],
            api_model=settings["api_model"],
        )

        with st.spinner("Running the MiniMind job agent..."):
            # 真正触发 Agent 执行的核心调用就在这一行。
            st.session_state["last_result"] = run_job_agent(**kwargs)
        # 重新渲染页面，让结果区和历史记录区立刻刷新。
        st.rerun()


def render_results_panel():
    """渲染 Agent 运行结果。"""

    result = st.session_state.get("last_result")
    if not result:
        # 第一次打开页面还没跑过 Agent 时，显示空状态提示。
        st.markdown(
            '<div class="result-shell"><div class="section-title">No Run Yet</div>'
            '<div class="mono-note">Use the sample inputs or paste your own JD and resume, then click "Run Job Agent".</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="result-shell">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Run Outcome</div>', unsafe_allow_html=True)

    metrics = st.columns(4, gap="medium")
    with metrics[0]:
        render_metric("Match Score", str(result["match_score"]), "Heuristic fit score from required skill overlap")
    with metrics[1]:
        # 给不同决策配上不同颜色，让用户一眼看出结果类型。
        status_class = f"status-chip status-{result['apply_decision']}"
        render_metric("Decision", result["apply_decision"], "Graph route selected for the application")
        st.markdown(f'<span class="{status_class}">{result["apply_decision"]}</span>', unsafe_allow_html=True)
    with metrics[2]:
        missing = len(result.get("missing_skills", []))
        render_metric("Missing Skills", str(missing), ", ".join(result.get("missing_skills", [])) or "None")
    with metrics[3]:
        render_metric("Application ID", str(result["application_id"]), "Saved SQLite record id")

    resume_tab, letter_tab, raw_tab = st.tabs(["Rewritten Resume", "Cover Letter", "Raw Result"])
    with resume_tab:
        st.text_area("Rewritten Resume Output", value=result["rewritten_resume"], height=340)
    with letter_tab:
        st.text_area("Cover Letter Output", value=result["cover_letter"], height=260)
    with raw_tab:
        st.json(result)

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    """页面主入口。

    你可以把执行顺序记成：
    1. 配置页面
    2. 应用样式
    3. 准备默认状态
    4. 渲染标题
    5. 渲染侧边栏
    6. 渲染输入区
    7. 渲染结果区
    """

    st.set_page_config(page_title="MiniMind Job Agent", page_icon=":briefcase:", layout="wide")
    apply_page_style()
    ensure_session_defaults()
    render_hero()
    settings = render_settings_panel()
    render_input_panel(settings)
    render_results_panel()


if __name__ == "__main__":
    main()
