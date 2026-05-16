# Sales Copilot README Recruiting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md` into a Chinese-first recruiting-facing homepage for the Sales Copilot project, emphasizing LLM / RAG / evaluation capability without MiniMind-centric framing.

**Architecture:** This change is documentation-only. The implementation keeps the repository structure unchanged and rewrites the homepage content into a shorter project-intro format with seven sections: intro, core capabilities, system flow, evaluation design, code structure, quick start, and further reading. Validation focuses on content correctness, link/path consistency, and removal of internal-only benchmark language from the homepage.

**Tech Stack:** Markdown, GitHub README conventions, existing project docs under `docs/`, local PowerShell inspection commands

---

## File Map

- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Reference: `D:\minimind\.worktrees\minimind-job-agent\README_en.md`
- Reference: `D:\minimind\.worktrees\minimind-job-agent\docs\sales-copilot-retrospective.md`
- Reference: `D:\minimind\.worktrees\minimind-job-agent\docs\superpowers\specs\2026-05-16-sales-copilot-readme-recruiting-design.md`

### Task 1: Replace the homepage framing

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Reference: `D:\minimind\.worktrees\minimind-job-agent\docs\superpowers\specs\2026-05-16-sales-copilot-readme-recruiting-design.md`

- [ ] **Step 1: Capture the current README before rewriting**

Run:

```powershell
Get-Content 'D:\minimind\.worktrees\minimind-job-agent\README.md' -TotalCount 260
```

Expected: The current README still reads like a long technical project page with deep evaluation detail near the top.

- [ ] **Step 2: Rewrite the title and project intro**

Replace the opening content with a short Chinese-first recruiting summary that:

- names the project `Sales Copilot`
- says the inputs are customer context and meeting notes
- says the outputs are structured parsing, follow-up planning, CRM write-back, and tasks
- explicitly frames the project as a workflow-oriented LLM agent rather than a single interaction demo

- [ ] **Step 3: Add a concise core-capabilities section**

Write a short section that covers:

- structured meeting-note parsing
- hybrid RAG over product knowledge and sales playbooks
- task generation grounded by `task_candidates`
- CRM / Tasks write-back
- Streamlit workbench with streaming visibility

- [ ] **Step 4: Add the system-flow section**

Write a compact one-line workflow description equivalent to:

```md
`customer profile -> meeting-note parsing -> retrieved context -> lead judgment -> follow-up plan -> CRM / Tasks write-back`
```

- [ ] **Step 5: Commit the framing rewrite**

```bash
git -C 'D:\minimind\.worktrees\minimind-job-agent' add README.md
git -C 'D:\minimind\.worktrees\minimind-job-agent' commit -m "docs: rewrite README intro for recruiting"
```

### Task 2: Rebuild the middle sections around evaluation and navigation

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Reference: `D:\minimind\.worktrees\minimind-job-agent\docs\sales-copilot-retrospective.md`

- [ ] **Step 1: Replace benchmark-heavy sections with a plain-language evaluation section**

Add a short section that says:

- public datasets are used for structured parsing validation
- self-built evaluation sets are used for retrieval and workflow quality validation
- evaluation covers parsing, retrieval quality, and final workflow outputs

Do not include:

- metric tables
- specific scores
- internal benchmark labels such as `dual-path retrieval benchmark`
- long per-benchmark command blocks

- [ ] **Step 2: Add a code-structure section**

Write a compact navigation section that describes:

- `sales_copilot/` as the main workflow implementation
- `evals/sales_copilot/` as the parsing / retrieval / workflow evaluation area
- `scripts/` as runtime and evaluation entrypoints
- `docs/` as retrospective and design documentation

- [ ] **Step 3: Replace path-heavy instructions with a minimal quick-start**

Use repo-relative examples only. Keep the quick start to three steps:

```md
1. Start the streaming API
2. Launch the Streamlit workbench
3. Open the browser page
```

Use commands in this style:

```powershell
python scripts/run_sales_copilot_stream_api.py --host 127.0.0.1 --port 8011
python -m streamlit run scripts/sales_copilot_web_demo.py --server.port 8501
```

- [ ] **Step 4: Add a further-reading section**

Add short pointers to:

- `docs/sales-copilot-retrospective.md`
- `docs/superpowers/specs/`

- [ ] **Step 5: Commit the structure rewrite**

```bash
git -C 'D:\minimind\.worktrees\minimind-job-agent' add README.md
git -C 'D:\minimind\.worktrees\minimind-job-agent' commit -m "docs: simplify README sections for GitHub homepage"
```

### Task 3: Review and verify the homepage quality

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Reference: `D:\minimind\.worktrees\minimind-job-agent\README_en.md`

- [ ] **Step 1: Verify forbidden content is gone from the homepage**

Run:

```powershell
Select-String -Path 'D:\minimind\.worktrees\minimind-job-agent\README.md' -Pattern 'MiniMind|dual-path retrieval benchmark|Recall@3|CRM acceptable rate|overall acceptable rate|D:\\anaconda|D:\\minimind'
```

Expected:

- no MiniMind-centric homepage framing
- no internal benchmark branding
- no score-first messaging
- no absolute local machine paths in the main README

- [ ] **Step 2: Verify the required sections exist**

Run:

```powershell
Get-Content 'D:\minimind\.worktrees\minimind-job-agent\README.md' -TotalCount 160
```

Expected: The README visibly includes sections for:

- project intro
- core capabilities
- system flow
- evaluation design
- code structure
- quick start
- further reading

- [ ] **Step 3: Manually skim the first screen of the README**

Run:

```powershell
Get-Content 'D:\minimind\.worktrees\minimind-job-agent\README.md' -TotalCount 120
```

Expected:

- the first screen reads like a recruiting-facing project summary
- the project purpose is visible within the first screen
- the repo no longer opens with long benchmark detail

- [ ] **Step 4: Commit the final README polish**

```bash
git -C 'D:\minimind\.worktrees\minimind-job-agent' add README.md
git -C 'D:\minimind\.worktrees\minimind-job-agent' commit -m "docs: polish README for recruiting review"
```

## Self-Review

### Spec coverage

- Project intro: covered in Task 1
- Core capabilities: covered in Task 1
- System flow: covered in Task 1
- Evaluation design without scores: covered in Task 2
- Code structure: covered in Task 2
- Quick start without path-heavy instructions: covered in Task 2
- Further reading: covered in Task 2
- Recruiter-oriented validation: covered in Task 3

### Placeholder scan

No `TODO`, `TBD`, or unresolved placeholders remain in the plan.

### Type and naming consistency

The plan consistently targets:

- `README.md`
- `docs/sales-copilot-retrospective.md`
- `docs/superpowers/specs/`

and uses the same section naming across implementation and verification.
