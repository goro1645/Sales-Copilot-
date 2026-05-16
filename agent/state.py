from typing import TypedDict


class JobAgentState(TypedDict, total=False):
    """LangGraph 各节点之间共享的状态字典。

    你可以把它理解成“整条工作流共用的一份上下文”。
    每个节点都会：
    - 读取自己需要的字段
    - 产出自己负责的新字段
    - 再把结果交给下一个节点

    这里选 `TypedDict` 而不是大类，有两个主要原因：
    - 对初学者来说更直观，本质上就是一个 dict
    - 节点可以只更新自己关心的字段，不需要维护一个很重的对象
    """

    # 输入类字段：通常由外部页面或 CLI 传进来
    company: str
    role: str
    job_posting: str
    resume_text: str

    # JD 解析阶段产出的字段
    job_summary: str
    required_skills: list[str]
    preferred_skills: list[str]

    # 简历评分阶段产出的字段
    matched_skills: list[str]
    missing_skills: list[str]
    preferred_hits: list[str]
    match_score: int

    # 生成阶段产出的字段
    rewritten_resume: str
    cover_letter: str

    # 最终决策字段
    apply_decision: str
