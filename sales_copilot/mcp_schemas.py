from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AccountRecord(BaseModel):
    id: int
    name: str
    industry: str
    size_segment: str
    status: str
    opportunity_stage: str
    last_contact_at: str | None = None
    created_at: str
    updated_at: str


class TaskRecord(BaseModel):
    id: int
    account_id: int
    meeting_id: int
    title: str
    description: str
    priority: str
    due_at: str
    status: str
    created_at: str
    updated_at: str


class AccountResponse(BaseModel):
    account: AccountRecord


class TaskListResponse(BaseModel):
    tasks: list[TaskRecord]


class TaskCreateResponse(BaseModel):
    task_id: int


class AccountUpdateResponse(BaseModel):
    account: AccountRecord


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_account": {
        "name": "get_account",
        "description": "Fetch the current CRM account state by account_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "Unique account identifier."},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    },
    "list_account_tasks": {
        "name": "list_account_tasks",
        "description": "List tasks for an account, optionally filtered by status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "Unique account identifier."},
                "status": {"type": "string", "description": "Optional task status filter."},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    },
    "create_task": {
        "name": "create_task",
        "description": "Create or refresh a follow-up task for an account meeting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer"},
                "meeting_id": {"type": "integer"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string"},
                "due_at": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["account_id", "meeting_id", "title", "description", "priority", "due_at"],
            "additionalProperties": False,
        },
    },
    "update_account_stage": {
        "name": "update_account_stage",
        "description": "Update account status, opportunity stage, and last contact date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer"},
                "status": {"type": "string"},
                "opportunity_stage": {"type": "string"},
                "last_contact_at": {"type": "string"},
            },
            "required": ["account_id", "status", "opportunity_stage", "last_contact_at"],
            "additionalProperties": False,
        },
    },
}
