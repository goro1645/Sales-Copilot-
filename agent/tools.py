"""一些不依赖大模型也能稳定运行的“基础工具函数”。

这个文件里的函数很适合新手先读，因为它们大多是确定性的：
- 输入什么
- 处理什么
- 输出什么

都比较清楚，不像 LLM 调用那样带有随机性。
"""

import re

from agent.schemas import ApplicationRecord


# 这些词在 JD 里很常见，但通常不能当成“技能关键词”。
# 例如 company / experience / strong / required 这类词出现频率很高，
# 如果不去掉，会把真正的技能词淹没掉。
JOB_POSTING_STOPWORDS = {
    "a",
    "ability",
    "an",
    "and",
    "around",
    "backend",
    "build",
    "building",
    "company",
    "data",
    "demos",
    "designing",
    "engineer",
    "engineering",
    "experience",
    "familiarity",
    "for",
    "frameworks",
    "in",
    "integrating",
    "is",
    "labs",
    "language",
    "lightweight",
    "looking",
    "models",
    "need",
    "needs",
    "of",
    "or",
    "other",
    "preferred",
    "practical",
    "products",
    "quality",
    "reliability",
    "required",
    "requirements",
    "role",
    "similar",
    "skills",
    "stores",
    "strong",
    "the",
    "to",
    "with",
    "workflows",
}


def extract_keywords(text: str) -> list[str]:
    """从文本里提取英文关键词，并保持第一次出现时的顺序。

    这里没有上复杂的 NLP，而是故意保持简单：
    - 全部转小写
    - 用正则抓英文单词
    - 去重但保留原始顺序

    这样做的好处是非常稳定，也便于写测试。
    """

    tokens = re.findall(r"[A-Za-z]+", text.lower())
    keywords: list[str] = []
    for token in tokens:
        if token not in keywords:
            keywords.append(token)
    return keywords


def score_resume_fit(
    *,
    resume_text: str,
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> dict:
    """用“关键词重合度”给简历和 JD 打分。

    这是当前项目里最容易理解的一种评分方式：
    1. 从简历里提关键词
    2. 看 required_skills 里哪些命中了
    3. 命中率 * 100，得到分数

    比如：
    - required skills 有 5 个
    - 命中了 4 个
    - 那 score = 80
    """

    preferred_skills = preferred_skills or []
    resume_keywords = set(extract_keywords(resume_text))

    # matched / missing / preferred_hits 这三类结果后面都会被前端展示，
    # 也会被 prompt 用来引导模型改写简历。
    matched_skills = [skill for skill in required_skills if skill.lower() in resume_keywords]
    missing_skills = [skill for skill in required_skills if skill.lower() not in resume_keywords]
    preferred_hits = [skill for skill in preferred_skills if skill.lower() in resume_keywords]

    score = 0
    if required_skills:
        score = int(len(matched_skills) / len(required_skills) * 100)

    return {
        "score": score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "preferred_hits": preferred_hits,
    }


def parse_job_description(job_posting: str) -> dict:
    """从 JD 里提取结构化字段。

    当前策略非常适合入门理解：
    1. 如果 JD 里有明确的 `Requirements` / `Preferred` 小节，就优先信这些结构
    2. 如果没有明显结构，就退回到全文关键词扫描

    这相当于一个“先用规则，规则不够再降级”的思路。
    """

    def filtered_keywords(text: str) -> list[str]:
        # 先做通用关键词提取，再去掉无意义的停用词。
        return [keyword for keyword in extract_keywords(text) if keyword not in JOB_POSTING_STOPWORDS]

    current_section = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []

    for raw_line in job_posting.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # 下面这段逻辑的目标是识别“当前正在读 JD 的哪个区块”。
        # 比如遇到 Requirements，后续的列表项都归到 required_skills。
        lowered = line.lower().lstrip("#").strip()
        if "requirement" in lowered or lowered == "required":
            current_section = "required"
            continue
        if "preferred" in lowered or "nice to have" in lowered:
            current_section = "preferred"
            continue
        if line.startswith("#"):
            current_section = None
            continue
        if not line.startswith(("-", "*")) or current_section is None:
            continue

        keywords = filtered_keywords(line[1:].strip())
        target = required_skills if current_section == "required" else preferred_skills
        for keyword in keywords:
            if keyword not in target:
                target.append(keyword)

    if not required_skills and not preferred_skills:
        # 如果整份 JD 没有明显的结构化标题，
        # 就把全文做一次简化关键词抽取，至少保证后续评分还能跑。
        required_skills = filtered_keywords(job_posting)

    return {
        "job_summary": job_posting.strip(),
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
    }


def rewrite_resume_for_job(
    *,
    resume_text: str,
    role: str,
    required_skills: list[str],
    matched_skills: list[str],
) -> str:
    """生成一个不依赖模型的简历改写兜底版本。

    它不是特别“聪明”，但足够稳定。
    这很适合 demo 和教学场景，因为你永远能看见一份输出。
    """

    highlighted = ", ".join(matched_skills or required_skills[:3])
    return (
        f"Tailored for {role}\n"
        f"{resume_text}\n\n"
        f"Relevant skills to highlight: {highlighted}"
    )


def generate_cover_letter(
    *,
    company: str,
    role: str,
    matched_skills: list[str],
) -> str:
    """生成一个固定模板的求职信兜底版本。"""

    skills_summary = ", ".join(matched_skills) or "relevant LLM application skills"
    return (
        f"Dear {company},\n\n"
        f"I am excited to apply for the {role} role. My background aligns well with "
        f"the following skills: {skills_summary}.\n\n"
        "Best regards,"
    )


def build_application_record(
    *,
    company: str,
    role: str,
    match_score: int,
    status: str,
    resume_version: str,
    cover_letter: str,
) -> dict:
    """构建一条经过 schema 校验的申请记录。

    这里先过一次 `ApplicationRecord`，
    是为了在真正写数据库之前，先保证字段结构是对的。
    """

    record = ApplicationRecord(
        company=company,
        role=role,
        match_score=match_score,
        status=status,
        resume_version=resume_version,
        cover_letter=cover_letter,
    )
    return record.model_dump()
