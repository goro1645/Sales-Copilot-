import importlib

from scripts.openai_api_utils import build_chat_prompt, parse_tool_call_response


class DummyTokenizer:
    def __init__(self):
        self.calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return "PREFIX::tool prompt payload"


def test_build_chat_prompt_passes_tools_into_chat_template():
    tokenizer = DummyTokenizer()
    messages = [{"role": "user", "content": "Find matching jobs for me"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_jobs",
                "description": "Search jobs by keyword",
                "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}}},
            },
        }
    ]

    prompt = build_chat_prompt(
        tokenizer=tokenizer,
        messages=messages,
        max_tokens=12,
        tools=tools,
    )

    assert prompt == "ompt payload"
    assert tokenizer.calls[0]["messages"] == messages
    assert tokenizer.calls[0]["tools"] == tools
    assert tokenizer.calls[0]["tokenize"] is False
    assert tokenizer.calls[0]["add_generation_prompt"] is True


def test_parse_tool_call_response_returns_openai_style_tool_call_payload():
    response_text = """<tool_call>
{"name": "search_jobs", "arguments": {"keyword": "langgraph"}}
</tool_call>"""

    parsed = parse_tool_call_response(response_text)

    assert parsed["content"] == ""
    assert parsed["tool_calls"][0]["type"] == "function"
    assert parsed["tool_calls"][0]["function"]["name"] == "search_jobs"
    assert parsed["tool_calls"][0]["function"]["arguments"] == '{"keyword": "langgraph"}'


def test_parse_tool_call_response_keeps_plain_text_answers_untouched():
    parsed = parse_tool_call_response("I found three suitable roles for you.")

    assert parsed == {
        "content": "I found three suitable roles for you.",
        "tool_calls": [],
    }


def test_serve_openai_api_module_can_be_imported_without_loading_torch_runtime():
    module = importlib.import_module("scripts.serve_openai_api")

    assert hasattr(module, "chat_completions")
