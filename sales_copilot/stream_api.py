from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm.deepseek_client import DeepSeekClient
from sales_copilot.mcp_client import SalesCopilotMCPClient
from sales_copilot.mcp_server import SalesCopilotMCPServer
from sales_copilot.runner import run_sales_copilot_stream
from sales_copilot.stream_sse import iter_sse_events


class SalesCopilotStreamRequest(BaseModel):
    customer_profile_text: str
    meeting_note_text: str
    database_path: str
    execution_mode: str = "direct"
    api_key: str
    api_base_url: str = "https://api.deepseek.com"
    api_model: str = "deepseek-chat"


def create_sales_copilot_stream_app(*, workflow_runner=run_sales_copilot_stream) -> FastAPI:
    app = FastAPI()

    @app.post("/sales-copilot/stream")
    def stream_route(request: SalesCopilotStreamRequest):
        llm_client = DeepSeekClient(
            api_key=request.api_key,
            base_url=request.api_base_url,
            model=request.api_model,
        )
        mcp_client = None
        if request.execution_mode == "mcp":
            mcp_client = SalesCopilotMCPClient(SalesCopilotMCPServer(Path(request.database_path)))

        events = workflow_runner(
            customer_profile_text=request.customer_profile_text,
            meeting_note_text=request.meeting_note_text,
            database_path=request.database_path,
            llm_client=llm_client,
            execution_mode=request.execution_mode,
            mcp_client=mcp_client,
        )
        return StreamingResponse(iter_sse_events(events), media_type="text/event-stream")

    return app
