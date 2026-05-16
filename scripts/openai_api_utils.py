import json
import re
from pathlib import Path


# MiniMind 在工具调用场景下，会把调用内容包在 <tool_call> ... </tool_call> 里。
# 这些常量分别服务于“整段解析”和“流式解析”两个路径。
TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
STREAM_OPEN_TAG = "<tool_call>"
STREAM_CLOSE_TAG = "</tool_call>"
STREAM_NAME_PATTERN = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
STREAM_ARGUMENTS_PATTERN = re.compile(r'"arguments"\s*:\s*')

# 这些都是“本地原生模型目录”的常见写法，我们统一视为同一种默认别名。
DEFAULT_MODEL_ALIASES = {"../model", "./model", "model"}


def _build_stream_content_chunk(text: str) -> dict:
    return {
        "choices": [{
            "delta": {"content": text}
        }]
    }


def _build_stream_tool_name_chunk(name: str) -> dict:
    # 先告诉客户端：这次流式输出不是普通文本，而是一次 function tool call。
    return {
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": "",
                    },
                }]
            }
        }]
    }


def _build_stream_tool_arguments_chunk(arguments_text: str) -> dict:
    return {
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "function": {
                        "arguments": arguments_text,
                    },
                }]
            }
        }]
    }


def _build_stream_finish_chunk(reason: str) -> dict:
    return {
        "choices": [{
            "delta": {},
            "finish_reason": reason,
        }]
    }


def _longest_tag_prefix_suffix(text: str, tag: str) -> int:
    """返回 text 末尾中，最长且也是 tag 前缀的那一段长度。

    这样可以避免模型刚开始输出 `<tool_call>` 时，
    我们把 `<to` 这种半截标签误当作普通 content 先流给前端。
    """

    max_len = min(len(text), len(tag) - 1)
    for length in range(max_len, 0, -1):
        if text.endswith(tag[:length]):
            return length
    return 0


class _JsonValueStreamState:
    """跟踪 arguments JSON 值是否已经开始、结束，以及当前扫描到了哪里。"""

    def __init__(self):
        self.started = False
        self.complete = False
        self.value_start: int | None = None
        self.complete_end: int | None = None
        self.kind: str | None = None
        self.depth = 0
        self.in_string = False
        self.escape = False

    def feed(self, text: str, start_index: int) -> int:
        for index in range(start_index, len(text)):
            char = text[index]

            if not self.started:
                if char.isspace():
                    continue

                self.started = True
                self.value_start = index
                if char in "{[":
                    self.kind = "structured"
                    self.depth = 1
                elif char == '"':
                    self.kind = "string"
                    self.in_string = True
                else:
                    self.kind = "primitive"
                continue

            if self.complete:
                break

            if self.kind == "structured":
                if self.in_string:
                    if self.escape:
                        self.escape = False
                    elif char == "\\":
                        self.escape = True
                    elif char == '"':
                        self.in_string = False
                    continue

                if char == '"':
                    self.in_string = True
                elif char in "{[":
                    self.depth += 1
                elif char in "}]":
                    self.depth -= 1
                    if self.depth == 0:
                        self.complete = True
                        self.complete_end = index + 1
                        break
            elif self.kind == "string":
                if self.escape:
                    self.escape = False
                elif char == "\\":
                    self.escape = True
                elif char == '"':
                    self.complete = True
                    self.complete_end = index + 1
                    break
            else:
                if char in ",}]":
                    self.complete = True
                    self.complete_end = index
                    break

        return len(text)


class OpenAIStreamEventAssembler:
    """把 MiniMind 的原始流式文本，转换成更接近 OpenAI SSE 的事件流。

    目标：
    1. 普通文本继续按 `delta.content` 流式输出
    2. `<tool_call>...</tool_call>` 不再作为普通文本裸输出
    3. 在流式场景下补出 `delta.tool_calls`
    4. 结束时把 `finish_reason` 从 `stop` / `tool_calls` 区分开
    """

    def __init__(self):
        self._content_buffer = ""
        self._tool_buffer = ""
        self._in_tool_call = False
        self._tool_name_emitted = False
        self._arguments_match_end: int | None = None
        self._arguments_scan_index = 0
        self._arguments_emitted_text = ""
        self._arguments_state = _JsonValueStreamState()
        self._completed_tool_call = False

    def push_text(self, text: str) -> list[dict]:
        if not text:
            return []

        if self._in_tool_call:
            self._tool_buffer += text
            return self._process_tool_buffer()

        self._content_buffer += text
        return self._process_content_buffer()

    def finalize(self) -> list[dict]:
        chunks: list[dict] = []

        if self._in_tool_call:
            # 如果标签没闭合，就把缓存内容按普通文本吐回去，避免静默丢失输出。
            self._content_buffer += STREAM_OPEN_TAG + self._tool_buffer
            self._reset_tool_state()

        if self._content_buffer:
            chunks.append(_build_stream_content_chunk(self._content_buffer))
            self._content_buffer = ""

        chunks.append(_build_stream_finish_chunk("tool_calls" if self._completed_tool_call else "stop"))
        return chunks

    def _process_content_buffer(self) -> list[dict]:
        chunks: list[dict] = []

        while self._content_buffer:
            open_index = self._content_buffer.find(STREAM_OPEN_TAG)
            if open_index != -1:
                plain_text = self._content_buffer[:open_index]
                if plain_text:
                    chunks.append(_build_stream_content_chunk(plain_text))

                self._tool_buffer += self._content_buffer[open_index + len(STREAM_OPEN_TAG):]
                self._content_buffer = ""
                self._in_tool_call = True
                chunks.extend(self._process_tool_buffer())
                continue

            holdback = _longest_tag_prefix_suffix(self._content_buffer, STREAM_OPEN_TAG)
            safe_length = len(self._content_buffer) - holdback
            if safe_length <= 0:
                break

            chunks.append(_build_stream_content_chunk(self._content_buffer[:safe_length]))
            self._content_buffer = self._content_buffer[safe_length:]
            break

        return chunks

    def _process_tool_buffer(self) -> list[dict]:
        chunks: list[dict] = []

        close_index = self._tool_buffer.find(STREAM_CLOSE_TAG)
        visible_text = self._tool_buffer if close_index == -1 else self._tool_buffer[:close_index]

        chunks.extend(self._emit_tool_call_chunks(visible_text))

        if close_index == -1:
            return chunks

        chunks.extend(self._flush_tool_call_remainder(visible_text))
        self._completed_tool_call = True

        trailing_text = self._tool_buffer[close_index + len(STREAM_CLOSE_TAG):]
        self._reset_tool_state()
        if trailing_text:
            self._content_buffer += trailing_text
            chunks.extend(self._process_content_buffer())
        return chunks

    def _emit_tool_call_chunks(self, visible_text: str) -> list[dict]:
        chunks: list[dict] = []

        if not self._tool_name_emitted:
            name_match = STREAM_NAME_PATTERN.search(visible_text)
            if name_match:
                tool_name = json.loads(f'"{name_match.group(1)}"')
                chunks.append(_build_stream_tool_name_chunk(tool_name))
                self._tool_name_emitted = True

        if not self._tool_name_emitted:
            return chunks

        if self._arguments_match_end is None:
            arguments_match = STREAM_ARGUMENTS_PATTERN.search(visible_text)
            if arguments_match:
                self._arguments_match_end = arguments_match.end()
                self._arguments_scan_index = self._arguments_match_end

        if self._arguments_match_end is None:
            return chunks

        self._arguments_scan_index = self._arguments_state.feed(visible_text, self._arguments_scan_index)
        if self._arguments_state.value_start is None:
            return chunks

        visible_end = self._arguments_state.complete_end if self._arguments_state.complete else len(visible_text)
        current_text = visible_text[self._arguments_state.value_start:visible_end]
        if self._arguments_emitted_text and current_text.startswith(self._arguments_emitted_text):
            delta_text = current_text[len(self._arguments_emitted_text):]
        elif not self._arguments_emitted_text:
            delta_text = current_text
        else:
            delta_text = ""

        if delta_text:
            chunks.append(_build_stream_tool_arguments_chunk(delta_text))
            self._arguments_emitted_text += delta_text

        return chunks

    def _flush_tool_call_remainder(self, visible_text: str) -> list[dict]:
        chunks: list[dict] = []
        payload = json.loads(visible_text.strip())

        if not self._tool_name_emitted:
            chunks.append(_build_stream_tool_name_chunk(payload["name"]))
            self._tool_name_emitted = True

        arguments = payload.get("arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)

        if arguments.startswith(self._arguments_emitted_text):
            remainder = arguments[len(self._arguments_emitted_text):]
        elif not self._arguments_emitted_text:
            remainder = arguments
        else:
            remainder = ""

        if remainder:
            chunks.append(_build_stream_tool_arguments_chunk(remainder))
            self._arguments_emitted_text += remainder

        return chunks

    def _reset_tool_state(self) -> None:
        self._tool_buffer = ""
        self._in_tool_call = False
        self._tool_name_emitted = False
        self._arguments_match_end = None
        self._arguments_scan_index = 0
        self._arguments_emitted_text = ""
        self._arguments_state = _JsonValueStreamState()


def build_chat_prompt(tokenizer, messages: list, max_tokens: int, tools: list | None = None) -> str:
    """用 MiniMind tokenizer 的 chat template 构造最终 prompt。

    不自己手拼字符串，而是直接复用 tokenizer 的 chat template，
    是为了尽量贴合模型训练时的输入格式。
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
    """把 MiniMind 的整段工具调用输出，转换成 OpenAI 风格结构。"""

    match = TOOL_CALL_PATTERN.search(response_text)
    if not match:
        return {
            "content": response_text,
            "tool_calls": [],
        }

    payload = json.loads(match.group(1))
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, str):
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


def default_runtime_paths(script_path: str | Path) -> dict[str, str]:
    """按项目根目录解析默认路径，而不是按当前终端目录解析。"""

    resolved_script = Path(script_path).resolve()
    for parent in resolved_script.parents:
        if parent.name == ".worktrees":
            project_root = parent.parent
            break
    else:
        project_root = resolved_script.parent.parent

    return {
        "project_root": str(project_root),
        "load_from": str(project_root / "model"),
        "save_dir": str(project_root / "out"),
    }


def resolve_runtime_args(args, script_path: str | Path):
    """把命令行参数里的路径标准化。"""

    runtime_paths = default_runtime_paths(script_path)
    project_root = Path(runtime_paths["project_root"])
    load_from = Path(args.load_from).expanduser()
    save_dir = Path(args.save_dir).expanduser()

    if load_from.is_absolute():
        args.load_from = str(load_from.resolve())
    elif load_from.as_posix() in DEFAULT_MODEL_ALIASES:
        args.load_from = runtime_paths["load_from"]
    else:
        repo_relative_load_from = (project_root / load_from).resolve()
        if repo_relative_load_from.exists():
            args.load_from = str(repo_relative_load_from)

    if save_dir.is_absolute():
        args.save_dir = str(save_dir.resolve())
    else:
        args.save_dir = str((project_root / save_dir).resolve())

    return args
