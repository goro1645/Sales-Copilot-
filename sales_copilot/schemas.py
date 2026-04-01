from pydantic import BaseModel, Field


class AccountRecord(BaseModel):
    name: str
    industry: str = ""
    size_segment: str = ""
    status: str
    opportunity_stage: str


class MeetingSummary(BaseModel):
    account_name: str
    customer_roles: list[str] = Field(default_factory=list)
    confirmed_needs: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class TaskRecord(BaseModel):
    account_name: str
    title: str
    description: str
    priority: str
    status: str
