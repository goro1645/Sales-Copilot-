import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.openai_api_utils import (
    OpenAIStreamEventAssembler,
    build_chat_prompt,
    default_runtime_paths,
    parse_tool_call_response,
    resolve_runtime_args,
)


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


def test_stream_event_assembler_keeps_plain_text_streaming_as_content():
    assembler = OpenAIStreamEventAssembler()

    chunks = []
    chunks.extend(assembler.push_text("Hello "))
    chunks.extend(assembler.push_text("world"))
    chunks.extend(assembler.finalize())

    content = "".join(
        choice["delta"].get("content", "")
        for payload in chunks
        for choice in payload.get("choices", [])
    )

    assert content == "Hello world"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_stream_event_assembler_emits_streaming_tool_call_delta():
    assembler = OpenAIStreamEventAssembler()

    fragments = [
        "<tool",
        "_call>{\"name\": \"search_jobs\", \"arguments\": {\"keyword\": ",
        "\"langgraph\"}}",
        "</tool_call>",
    ]

    chunks = []
    for fragment in fragments:
        chunks.extend(assembler.push_text(fragment))
    chunks.extend(assembler.finalize())

    tool_call_deltas = [
        choice["delta"]["tool_calls"][0]
        for payload in chunks
        for choice in payload.get("choices", [])
        if choice.get("delta", {}).get("tool_calls")
    ]
    content = "".join(
        choice["delta"].get("content", "")
        for payload in chunks
        for choice in payload.get("choices", [])
    )
    streamed_arguments = "".join(
        delta.get("function", {}).get("arguments", "")
        for delta in tool_call_deltas
    )

    assert tool_call_deltas
    assert tool_call_deltas[0]["function"]["name"] == "search_jobs"
    assert streamed_arguments == '{"keyword": "langgraph"}'
    assert "<tool_call>" not in content
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"


def test_serve_openai_api_module_can_be_imported_without_loading_torch_runtime():
    module = importlib.import_module("scripts.serve_openai_api")

    assert hasattr(module, "chat_completions")


def test_runtime_dependency_check_does_not_require_model_initialization():
    module = importlib.import_module("scripts.serve_openai_api")

    module.ensure_model_dependencies()


def test_default_runtime_paths_are_resolved_from_project_root():
    script_path = Path("D:/minimind/scripts/serve_openai_api.py")

    paths = default_runtime_paths(script_path)

    assert paths["load_from"] == str(Path("D:/minimind/model"))
    assert paths["save_dir"] == str(Path("D:/minimind/out"))


def test_default_runtime_paths_use_source_repo_root_for_worktree_scripts():
    script_path = Path("D:/minimind/.worktrees/minimind-job-agent/scripts/serve_openai_api.py")

    paths = default_runtime_paths(script_path)

    assert paths["project_root"] == str(Path("D:/minimind"))
    assert paths["load_from"] == str(Path("D:/minimind/model"))
    assert paths["save_dir"] == str(Path("D:/minimind/out"))


def test_resolve_runtime_args_rewrites_default_relative_paths_to_absolute_paths():
    args = SimpleNamespace(
        load_from="../model",
        save_dir="out",
        weight="full_sft",
        lora_weight="None",
    )

    resolved = resolve_runtime_args(
        args=args,
        script_path=Path("D:/minimind/scripts/serve_openai_api.py"),
    )

    assert resolved.load_from == str(Path("D:/minimind/model"))
    assert resolved.save_dir == str(Path("D:/minimind/out"))


def test_generate_stream_response_emits_tool_call_chunks(monkeypatch):
    module = importlib.import_module("scripts.serve_openai_api")

    class DummyInputs(dict):
        def __init__(self):
            super().__init__(input_ids=[[1]], attention_mask=[[1]])
            self.input_ids = [[1]]
            self.attention_mask = [[1]]

        def to(self, _device):
            return self

    class DummyTokenizer:
        pad_token_id = 0
        eos_token_id = 1

        def apply_chat_template(self, messages, **kwargs):
            return "prompt"

        def __call__(self, prompt, return_tensors=None, truncation=None):
            return DummyInputs()

    class DummyStreamer:
        def __init__(self, tokenizer, queue):
            self.queue = queue

        def on_finalized_text(self, text, stream_end=False):
            self.queue.put(text)
            if stream_end:
                self.queue.put(None)

    class DummyModel:
        def generate(self, *args, **kwargs):
            streamer = kwargs["streamer"]
            streamer.on_finalized_text('<tool_call>{"name": "search_jobs", ')
            streamer.on_finalized_text('"arguments": {"keyword": "langgraph"}}', stream_end=False)
            streamer.on_finalized_text('</tool_call>', stream_end=True)

    monkeypatch.setattr(module, "tokenizer", DummyTokenizer())
    monkeypatch.setattr(module, "model", DummyModel())
    monkeypatch.setattr(module, "device", "cpu")
    monkeypatch.setattr(module, "CustomStreamer", DummyStreamer)

    chunks = [
        json.loads(chunk)
        for chunk in module.generate_stream_response(
            messages=[{"role": "user", "content": "Find jobs"}],
            temperature=0.7,
            top_p=0.9,
            max_tokens=32,
            tools=[{"type": "function", "function": {"name": "search_jobs"}}],
        )
    ]

    tool_call_deltas = [
        choice["delta"]["tool_calls"][0]
        for payload in chunks
        for choice in payload.get("choices", [])
        if choice.get("delta", {}).get("tool_calls")
    ]
    content = "".join(
        choice["delta"].get("content", "")
        for payload in chunks
        for choice in payload.get("choices", [])
    )

    assert tool_call_deltas
    assert tool_call_deltas[0]["function"]["name"] == "search_jobs"
    assert "<tool_call>" not in content
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"
