import json
import re


TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def build_chat_prompt(tokenizer, messages: list, max_tokens: int, tools: list | None = None) -> str:
    """Build the model prompt using MiniMind's chat template.

    The tokenizer already knows how to inject tool schemas into the prompt. We keep that logic
    here so the FastAPI layer stays focused on request/response handling.
    """

    template_kwargs = {
        "tokenize": False,
        "add_generation_prompt": True,
    }
    if tools:
        template_kwargs["tools"] = tools

    prompt = tokenizer.apply_chat_template(messages, **template_kwargs)
    return prompt[-max_tokens:]


def parse_tool_call_response(response_text: str) -> dict:
    """Convert MiniMind's XML-tagged tool call output into OpenAI-style payloads."""

    match = TOOL_CALL_PATTERN.search(response_text)
    if not match:
        return {
            "content": response_text,
            "tool_calls": [],
        }

    payload = json.loads(match.group(1))
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, str):
        # OpenAI-style tool calls carry arguments as a JSON string, so we normalize here once.
        arguments = json.dumps(arguments, ensure_ascii=False)

    return {
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": payload["name"],
                    "arguments": arguments,
                },
            }
        ],
    }
