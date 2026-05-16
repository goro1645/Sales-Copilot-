"""LangGraph 工作流定义。

如果说 `runner.py` 是总入口，这个文件就是“流程图本体”。
它负责定义每个节点做什么，以及节点之间如何跳转。

这版图故意保持很小，便于学习：
1. 解析 JD
2. 计算匹配分
3. 根据匹配分分流
   - 分低：reject
   - 分中：rewrite_resume
   - 分高：ready_to_apply
"""

from langgraph.graph import END, StateGraph

from agent.state import JobAgentState
from agent.tools import (
    generate_cover_letter,
    parse_job_description,
    rewrite_resume_for_job,
    score_resume_fit,
)


def _generate_rewritten_resume(state: JobAgentState, content_generator=None) -> str:
    """生成改写后的简历文本。

    这里有两条路径：
    - 没有真实 LLM 服务时：走 deterministic fallback
    - 有真实 LLM 服务时：优先调 MiniMind，失败再回退
    """

    # fallback 的意义是：即使 MiniMind 没启动、网络报错、生成异常，
    # 整个 Agent 依然能跑通，不会因为一个节点失败就整条链断掉。
    fallback = rewrite_resume_for_job(
        resume_text=state["resume_text"],
        role=state["role"],
        required_skills=state.get("required_skills", []),
        matched_skills=state.get("matched_skills", []),
    )
    if content_generator is None:
        return fallback

    try:
        generated = content_generator.rewrite_resume(
            role=state["role"],
            resume_text=state["resume_text"],
            required_skills=state.get("required_skills", []),
            matched_skills=state.get("matched_skills", []),
            missing_skills=state.get("missing_skills", []),
        )
        return generated.strip() or fallback
    except Exception:
        # 这里故意吞掉异常并回退，原因是图工作流更重视“流程跑完”。
        # 对演示项目来说，一个节点失败时还能拿到退化结果，比整个页面报错更友好。
        return fallback


def _generate_cover_letter(state: JobAgentState, content_generator=None) -> str:
    """生成求职信，策略和简历改写类似：优先调模型，失败时回退。"""

    fallback = generate_cover_letter(
        company=state["company"],
        role=state["role"],
        matched_skills=state.get("matched_skills", []),
    )
    if content_generator is None:
        return fallback

    try:
        generated = content_generator.generate_cover_letter(
            company=state["company"],
            role=state["role"],
            matched_skills=state.get("matched_skills", []),
            resume_text=state["resume_text"],
        )
        return generated.strip() or fallback
    except Exception:
        return fallback


def prepare_job_node(state: JobAgentState) -> dict:
    """准备岗位信息节点。

    这个节点的任务是：把 JD 里能提炼出的结构化信息先补齐，比如：
    - required_skills
    - preferred_skills
    - job_summary

    如果调用方已经提前传了 `required_skills`，这里就不重复解析。
    """

    if state.get("required_skills"):
        return {
            "job_summary": state.get("job_summary", state["job_posting"]),
            "preferred_skills": state.get("preferred_skills", []),
        }
    return parse_job_description(state["job_posting"])


def score_fit_node(state: JobAgentState) -> dict:
    """计算“这份简历和岗位的匹配程度”。

    这里先走最稳定、最好解释的关键词重合策略。
    优点是：
    - 好测
    - 好解释
    - 不依赖模型
    - 方便以后和模型评分混合
    """

    result = score_resume_fit(
        resume_text=state["resume_text"],
        required_skills=state.get("required_skills", []),
        preferred_skills=state.get("preferred_skills", []),
    )
    return {
        "match_score": result["score"],
        "matched_skills": result["matched_skills"],
        "missing_skills": result["missing_skills"],
        "preferred_hits": result["preferred_hits"],
    }


def route_after_scoring(state: JobAgentState) -> str:
    """根据匹配分决定下一步走哪个分支。

    这就是 LangGraph 里最重要的“条件路由”。
    你可以把它理解成普通代码里的 if / elif / else，
    只是这里返回的是“下一个节点名字”。
    """

    score = state["match_score"]
    if score < 60:
        return "reject"
    if score < 80:
        return "rewrite_resume"
    return "ready_to_apply"


def reject_node(state: JobAgentState) -> dict:
    """低匹配时的结束节点。

    这里仍然把原始简历回填到 `rewritten_resume`，
    是为了让前端展示结构保持一致，不必为 reject 单独写一套 UI。
    """

    return {
        "apply_decision": "reject",
        "rewritten_resume": state.get("resume_text", ""),
        "cover_letter": "",
    }


def rewrite_resume_node(state: JobAgentState, content_generator=None) -> dict:
    """中等匹配时：先建议改简历，不直接进入 ready_to_apply。"""

    return {
        "apply_decision": "rewrite_resume",
        "rewritten_resume": _generate_rewritten_resume(state, content_generator),
        "cover_letter": "",
    }


def ready_to_apply_node(state: JobAgentState, content_generator=None) -> dict:
    """高匹配时：同时生成改写简历和求职信。"""

    return {
        "apply_decision": "ready_to_apply",
        "rewritten_resume": _generate_rewritten_resume(state, content_generator),
        "cover_letter": _generate_cover_letter(state, content_generator),
    }


def build_job_agent_graph(content_generator=None):
    """构建并编译整张 Job Agent 图。

    这里的 `builder` 可以理解成“画流程图的工具”：
    - `add_node(...)`：添加节点
    - `add_edge(...)`：添加固定边
    - `add_conditional_edges(...)`：添加条件分支
    - `compile()`：把图编译成可执行对象
    """

    builder = StateGraph(JobAgentState)
    builder.add_node("prepare_job", prepare_job_node)
    builder.add_node("score_fit", score_fit_node)
    builder.add_node("reject", reject_node)
    # 这里用 lambda 把 `content_generator` 这个外部对象“带进节点里”。
    # 因为 LangGraph 节点函数默认只接收 state，所以我们用这种写法做一层包装。
    builder.add_node("rewrite_resume", lambda state: rewrite_resume_node(state, content_generator))
    builder.add_node("ready_to_apply", lambda state: ready_to_apply_node(state, content_generator))

    # 先从 prepare_job 开始执行。
    builder.set_entry_point("prepare_job")
    # prepare_job 执行完，一定进入 score_fit。
    builder.add_edge("prepare_job", "score_fit")
    # score_fit 执行完，不是固定下一步，而是要看匹配分动态路由。
    builder.add_conditional_edges(
        "score_fit",
        route_after_scoring,
        {
            "reject": "reject",
            "rewrite_resume": "rewrite_resume",
            "ready_to_apply": "ready_to_apply",
        },
    )
    # 这三个节点都是终点，执行完后图就结束。
    builder.add_edge("reject", END)
    builder.add_edge("rewrite_resume", END)
    builder.add_edge("ready_to_apply", END)
    return builder.compile()
