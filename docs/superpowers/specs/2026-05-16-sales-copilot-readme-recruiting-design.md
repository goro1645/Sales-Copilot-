# Sales Copilot README Recruiting Design

## Goal

Rewrite the repository homepage README so it works as a recruiting-facing project entry for the `Sales Copilot` branch work rather than a generic MiniMind subproject page.

The new README should help a hiring reviewer understand, within roughly 30 seconds:

- what the project is
- what technical problems it solves
- which LLM / RAG / evaluation capabilities were built
- where the important code lives
- how to run the smallest demo path

This README is not intended to be a full benchmark report, paper appendix, or development diary.

## Audience

Primary audience:

- recruiters
- hiring managers
- interviewers doing a fast GitHub scan

Secondary audience:

- engineers who want to open the repo and find the main implementation folders quickly

## Positioning

The README should present the project as:

- a sales follow-up LLM agent
- a workflow-centered system rather than a single chat demo
- a project that combines structured extraction, retrieval, task generation, and evaluation

The README should not foreground:

- the broader `MiniMind` training project
- internal benchmark naming that requires project context
- long historical experiment logs
- detailed metric tables on the homepage

## Content Changes

### Keep

- the project name `Sales Copilot`
- a short description of the end-to-end workflow
- mention of public datasets and self-built evaluation sets
- pointers to deeper technical docs

### Remove or De-emphasize

- MiniMind-centric framing
- detailed benchmark subsections on the homepage
- raw metric dumps
- overly internal evaluation names such as `dual-path retrieval benchmark`
- absolute local filesystem paths in primary quick-start content

## Target README Structure

### 1. Project Intro

A short Chinese introduction that explains:

- this is a sales follow-up LLM agent
- the main inputs are customer context and meeting notes
- the main outputs are structured extraction, follow-up planning, CRM write-back, and tasks

### 2. Core Capabilities

Use concise bullets that emphasize capability rather than metrics:

- structured meeting-note parsing
- hybrid RAG over product knowledge and sales playbooks
- task generation grounded by `task_candidates`
- CRM / Tasks write-back
- Streamlit workbench with streaming execution visibility

### 3. System Flow

Include a simple one-line workflow:

`customer profile -> meeting-note parsing -> retrieved context -> lead judgment -> follow-up plan -> CRM / Tasks write-back`

This section should stay short and readable.

### 4. Evaluation Design

Describe evaluation in plain language only:

- public datasets are used for structured parsing validation
- self-built evaluation sets are used for workflow quality validation
- evaluation covers parsing, retrieval quality, and final workflow outputs

Do not include:

- score tables
- internal benchmark branding
- detailed metric formulas

### 5. Code Structure

Briefly describe the most important folders:

- `sales_copilot/`
- `evals/sales_copilot/`
- `scripts/`
- `docs/`

This section should help a reviewer navigate the code quickly.

### 6. Quick Start

Keep only the smallest useful entry path:

- start the streaming API
- launch the Streamlit workbench
- open the browser page

Commands should be generic and repo-relative where possible. Avoid personal machine paths in the main README.

### 7. Further Reading

Point to:

- `docs/sales-copilot-retrospective.md`
- selected design docs under `docs/superpowers/specs/`

This lets the homepage stay clean while preserving depth for deeper review.

## Writing Style

The README should be:

- Chinese-first
- concise
- recruiting-friendly
- technically credible without sounding like an internal lab note

It should favor:

- short paragraphs
- flat bullet lists
- clear terminology

It should avoid:

- overly academic subsectioning
- unexplained internal jargon
- long path-heavy setup instructions at the top

## Non-Goals

This change does not:

- rename folders
- change implementation code
- remove detailed evaluation docs from the repo
- rewrite every branch-specific document

It is strictly a homepage presentation redesign.

## Success Criteria

The README is successful if:

- a recruiter can understand the project purpose quickly
- the repo homepage clearly highlights LLM / RAG / evaluation work
- the page no longer reads like a MiniMind submodule note
- a technical reader can find the main code and demo entrypoints without digging through internal docs
