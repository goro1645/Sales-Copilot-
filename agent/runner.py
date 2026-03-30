from pathlib import Path

from agent.prompts import build_cover_letter_messages, build_resume_rewrite_messages
from agent.graph import build_job_agent_graph
from agent.storage import save_application_record

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None


class MiniMindAPIGenerator:
    """Generate resume rewrites and cover letters through MiniMind's OpenAI-style endpoint.

    This class is intentionally tiny: prompt construction stays in `agent.prompts`, while this
    wrapper only handles transport and response extraction.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8998/v1",
        api_key: str = "minimind",
        model: str = "minimind",
    ):
        if OpenAI is None:
            raise RuntimeError("openai package is required for MiniMind API generation.")

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _complete(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=512,
            top_p=0.9,
        )
        return response.choices[0].message.content or ""

    def rewrite_resume(
        self,
        *,
        role: str,
        resume_text: str,
        required_skills: list[str],
        matched_skills: list[str],
        missing_skills: list[str],
    ) -> str:
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
    """Run the current graph once and persist the final decision.

    This wrapper gives the demo and later UI a single entrypoint. Keeping orchestration here
    avoids spreading graph invocation and SQLite code across multiple scripts.
    """

    if generator is None and use_api_generation:
        generator = MiniMindAPIGenerator(
            base_url=api_base_url,
            api_key=api_key,
            model=api_model,
        )

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

    resume_version = "resume_auto_v1"
    if result.get("apply_decision") == "reject":
        resume_version = "resume_original"

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
    result["application_id"] = application_id
    return result
