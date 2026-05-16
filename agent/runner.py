"""Job Agent 的统一运行入口。

这一层可以把它理解成“总调度器”：
1. 决定要不要接入真实 MiniMind API
2. 构建 LangGraph 工作流
3. 执行一次完整的求职任务
4. 把最终结果落到 SQLite，方便后续在页面里查看历史记录

把这些步骤集中在一个文件里，有两个好处：
- CLI、网页、后续接口都可以复用同一个入口
- 学代码时，你只要先看这个文件，就能抓住整个项目主线
"""

from pathlib import Path

import requests

from agent.prompts import build_cover_letter_messages, build_resume_rewrite_messages
from agent.graph import build_job_agent_graph
from agent.storage import save_application_record


class MiniMindAPIGenerator:
    """通过 MiniMind 的 OpenAI 风格接口，生成简历改写和求职信。

    这里故意做得很薄，只负责“发请求”和“取结果”：
    - Prompt 怎么拼，不放在这里，而是放在 `agent.prompts`
    - LangGraph 怎么编排，也不放在这里，而是放在 `agent.graph`

    这样拆分后，每个文件的职责都比较单一，新手读起来也更清楚。

    我们这里直接用 `requests.post(...)`，而不是官方 OpenAI SDK，
    是因为 MiniMind 提供的是一个“兼容 OpenAI 风格”的轻量接口，
    直接发 HTTP 请求更直观，也更容易排查问题。
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8998/v1",
        api_key: str = "minimind",
        model: str = "minimind",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def _complete(self, messages: list[dict]) -> str:
        """向本地 MiniMind 服务发送一次对话请求，并取回模型文本。

        `messages` 的结构和 OpenAI Chat Completions 类似，例如：
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
        ]

        这个函数只返回模型生成的纯文本，不负责业务含义解释。
        """

        response = requests.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 512,
                "top_p": 0.9,
                "stream": False,
            },
            timeout=120,
        )
        # 如果 HTTP 状态码不是 2xx，这里会直接抛异常，
        # 上层 graph 会自动回退到 deterministic fallback，避免整个流程中断。
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"] or ""

    def rewrite_resume(
        self,
        *,
        role: str,
        resume_text: str,
        required_skills: list[str],
        matched_skills: list[str],
        missing_skills: list[str],
    ) -> str:
        # 先把“岗位 + 简历 + 技能差距”组织成模型更容易理解的 messages，
        # 再交给 `_complete` 统一发送请求。
        messages = build_resume_rewrite_messages(
            role=role,
            resume_text=resume_text,
            required_skills=required_skills,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
        )
        return self._complete(messages)

    def generate_cover_letter(
        self,
        *,
        company: str,
        role: str,
        matched_skills: list[str],
        resume_text: str,
    ) -> str:
        # 求职信生成和简历改写走的是同一套调用链：
        # prompt builder -> HTTP 请求 -> 取回文本
        messages = build_cover_letter_messages(
            company=company,
            role=role,
            matched_skills=matched_skills,
            resume_text=resume_text,
        )
        return self._complete(messages)


def run_job_agent(
    *,
    company: str,
    role: str,
    job_posting: str,
    resume_text: str,
    database_path,
    required_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
    generator=None,
    use_api_generation: bool = False,
    api_base_url: str = "http://127.0.0.1:8998/v1",
    api_key: str = "minimind",
    api_model: str = "minimind",
) -> dict:
    """执行一次完整的 Job Agent 工作流，并把结果保存下来。

    你可以把它理解成整个应用最常用的“总入口函数”。

    外部页面或脚本只需要准备好：
    - 公司名
    - 岗位名
    - JD 文本
    - 简历文本

    然后直接调用这个函数，就能拿到：
    - 匹配分
    - 决策结果
    - 改写后的简历
    - 求职信
    - SQLite 里的记录 ID
    """

    if generator is None and use_api_generation:
        # 如果用户没手动传入生成器，但开启了 API 生成模式，
        # 这里就自动创建一个基于 MiniMind 服务的生成器。
        generator = MiniMindAPIGenerator(
            base_url=api_base_url,
            api_key=api_key,
            model=api_model,
        )

    # 这里构建的是一张 LangGraph 图。
    # 图里会定义：先解析 JD，再算匹配分，最后根据分数走不同分支。
    graph = build_job_agent_graph(content_generator=generator)
    result = graph.invoke(
        {
            "company": company,
            "role": role,
            "job_posting": job_posting,
            "resume_text": resume_text,
            "required_skills": required_skills or [],
            "preferred_skills": preferred_skills or [],
        }
    )

    # 这里用一个很简单的版本号策略：
    # - 如果直接 reject，就说明没必要生成新的简历版本，仍然记为 original
    # - 否则默认记成自动改写出来的 v1
    resume_version = "resume_auto_v1"
    if result.get("apply_decision") == "reject":
        resume_version = "resume_original"

    # 把本次运行结果存到 SQLite，方便网页展示历史记录。
    application_id = save_application_record(
        db_path=Path(database_path),
        record={
            "company": company,
            "role": role,
            "match_score": result["match_score"],
            "status": result["apply_decision"],
            "resume_version": resume_version,
            "cover_letter": result.get("cover_letter", ""),
        },
    )
    # 把数据库生成的主键 id 回填到结果里，
    # 这样前端可以直接展示“这是第几次申请记录”。
    result["application_id"] = application_id
    return result
