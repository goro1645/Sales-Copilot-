from pathlib import Path


def load_sample_documents(data_dir) -> dict:
    """读取网页 demo 自带的样例 JD 和样例简历。

    如果把文件读取直接写在 Streamlit 页面里，页面函数会变得很长。
    拆到工具函数后，主页面代码会更像“业务流程”。
    """

    data_dir = Path(data_dir)
    return {
        "job_posting": (data_dir / "sample_jd.md").read_text(encoding="utf-8"),
        "resume_text": (data_dir / "sample_resume.md").read_text(encoding="utf-8"),
    }


def build_runner_kwargs(
    *,
    company: str,
    role: str,
    job_posting: str,
    resume_text: str,
    database_path: str,
    use_api_generation: bool,
    api_base_url: str,
    api_key: str,
    api_model: str,
) -> dict:
    """把网页输入整理成 `run_job_agent` 需要的参数字典。

    这样做的好处是前端页面不必知道 runner 的所有细节，
    页面只负责采集输入，真正的参数整理在这里统一完成。
    """

    kwargs = {
        "company": company,
        "role": role,
        "job_posting": job_posting,
        "resume_text": resume_text,
        "database_path": database_path,
        "use_api_generation": use_api_generation,
    }
    if use_api_generation:
        # 只有开启 API 生成模式时，才把这些服务参数传下去。
        # 这样 deterministic fallback 模式会更干净。
        kwargs.update(
            {
                "api_base_url": api_base_url,
                "api_key": api_key,
                "api_model": api_model,
            }
        )
    return kwargs


def build_history_rows(rows: list[dict]) -> list[dict]:
    """把数据库原始记录转成适合前端表格展示的格式。"""

    return [
        {
            "ID": row["id"],
            "Company": row["company"],
            "Role": row["role"],
            "Score": row["match_score"],
            "Status": row["status"],
            "Resume Version": row["resume_version"],
            "Created At": row["created_at"],
        }
        for row in rows
    ]
