from llm.streaming import StreamToolCallAssembler


def test_stream_tool_call_assembler_accumulates_arguments_and_finishes():
    assembler = StreamToolCallAssembler()

    first = assembler.push_delta(index=0, tool_id="call_1", name="search_jobs", arguments_delta="")
    second = assembler.push_delta(index=0, tool_id=None, name=None, arguments_delta='{"keyword": "lang')
    third = assembler.push_delta(index=0, tool_id=None, name=None, arguments_delta='graph"}')
    finished = assembler.finish(index=0)

    assert first == [
        {
            "type": "tool_call_delta",
            "index": 0,
            "id": "call_1",
            "name": "search_jobs",
            "arguments_delta": "",
        }
    ]
    assert second[-1]["arguments_delta"] == '{"keyword": "lang'
    assert third[-1]["arguments_delta"] == 'graph"}'
    assert finished == {
        "type": "tool_call_finished",
        "index": 0,
        "id": "call_1",
        "name": "search_jobs",
        "arguments": '{"keyword": "langgraph"}',
    }
