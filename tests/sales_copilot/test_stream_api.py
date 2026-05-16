from fastapi.testclient import TestClient

from sales_copilot.stream_api import create_sales_copilot_stream_app


def test_stream_api_returns_sse_frames_from_workflow_events():
    def fake_runner(**kwargs):
        del kwargs
        yield {"type": "workflow_started", "workflow_name": "sales_copilot", "execution_mode": "direct"}
        yield {"type": "workflow_finished", "result": {"lead_priority": "high"}}

    app = create_sales_copilot_stream_app(workflow_runner=fake_runner)
    client = TestClient(app)

    with client.stream(
        "POST",
        "/sales-copilot/stream",
        json={
            "customer_profile_text": "Acme",
            "meeting_note_text": "Need proposal",
            "database_path": "tmp.db",
            "api_key": "test-key",
        },
    ) as response:
        body = "\n".join(
            chunk.decode() if isinstance(chunk, bytes) else chunk
            for chunk in response.iter_lines()
        )

    assert response.status_code == 200
    assert "event: workflow_started" in body
    assert "event: workflow_finished" in body
