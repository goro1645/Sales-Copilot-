"""MiniMind 的 OpenAI 兼容服务入口。

这个脚本做两件事：
1. 把本地 MiniMind 模型包装成 `/v1/chat/completions`
2. 兼容普通文本回复和 tool call 回复

这次额外补上的重点是：
- 非流式模式下，继续像以前一样在整段输出后解析 `<tool_call>...</tool_call>`
- 流式模式下，不再把 `<tool_call>` 原样吐给前端，而是边生成边组装成
  OpenAI 风格的 `delta.tool_calls`
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path
from queue import Queue
from threading import Thread

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.openai_api_utils import (
    OpenAIStreamEventAssembler,
    build_chat_prompt,
    default_runtime_paths,
    parse_tool_call_response,
    resolve_runtime_args,
)

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

    from model.model_lora import apply_lora, load_lora
    from model.model_minimind import MiniMindConfig, MiniMindForCausalLM
except ModuleNotFoundError:
    # 测试里经常只会 import 这个模块，不会真的启动模型。
    # 这里不要在 import 阶段直接崩掉，让测试有机会单独验证接口逻辑。
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    TextStreamer = None
    MiniMindConfig = None
    MiniMindForCausalLM = None
    apply_lora = None
    load_lora = None

warnings.filterwarnings("ignore")

app = FastAPI()
device = "cpu"
model = None
tokenizer = None


def ensure_model_dependencies() -> None:
    """确认运行时依赖已经安装。

    这里只检查包本身是否存在，不要求模型已经初始化。
    这样测试在“只导入模块、不启动模型”时仍然能跑通。
    """

    if torch is None or AutoTokenizer is None or MiniMindForCausalLM is None:
        raise RuntimeError(
            "MiniMind service runtime is not ready. Please install torch and model dependencies "
            "before starting the API server."
        )


def ensure_runtime_ready() -> None:
    """在真正处理请求前，确认模型和 tokenizer 都已经可用。"""

    ensure_model_dependencies()
    if model is None or tokenizer is None:
        raise RuntimeError("MiniMind model is not initialized. Start the API script from __main__ first.")


def init_model(args):
    """根据命令行参数加载模型和 tokenizer。"""

    ensure_model_dependencies()
    runtime_tokenizer = AutoTokenizer.from_pretrained(args.load_from)

    if "model" in args.load_from:
        # 这个分支表示加载 MiniMind 原生 torch 权重。
        moe_suffix = "_moe" if args.use_moe else ""
        save_dir = Path(args.save_dir)
        checkpoint_path = save_dir / f"{args.weight}_{args.hidden_size}{moe_suffix}.pth"
        runtime_model = MiniMindForCausalLM(
            MiniMindConfig(
                hidden_size=args.hidden_size,
                num_hidden_layers=args.num_hidden_layers,
                max_seq_len=args.max_seq_len,
                use_moe=bool(args.use_moe),
                inference_rope_scaling=args.inference_rope_scaling,
            )
        )
        runtime_model.load_state_dict(torch.load(str(checkpoint_path), map_location=device), strict=True)
        if args.lora_weight != "None":
            apply_lora(runtime_model)
            load_lora(runtime_model, str(save_dir / "lora" / f"{args.lora_weight}_{args.hidden_size}.pth"))
    else:
        # 这个分支表示直接加载 transformers 格式目录。
        runtime_model = AutoModelForCausalLM.from_pretrained(args.load_from, trust_remote_code=True)

    total_params_million = sum(parameter.numel() for parameter in runtime_model.parameters()) / 1e6
    print(f"MiniMind模型参数量: {total_params_million:.2f} M(illion)")
    return runtime_model.eval().to(device), runtime_tokenizer


class ChatRequest(BaseModel):
    """OpenAI `/v1/chat/completions` 兼容请求体。"""

    model: str
    messages: list
    temperature: float = 0.7
    top_p: float = 0.92
    max_tokens: int = 8192
    stream: bool = False
    tools: list = Field(default_factory=list)


class CustomStreamer(TextStreamer if TextStreamer is not None else object):
    """把 transformers 逐段输出塞进队列，供 StreamingResponse 读取。"""

    def __init__(self, runtime_tokenizer, queue: Queue):
        if TextStreamer is None:
            raise RuntimeError("Transformers runtime is unavailable for streaming generation.")
        super().__init__(runtime_tokenizer, skip_prompt=True, skip_special_tokens=True)
        self.queue = queue

    def on_finalized_text(self, text: str, stream_end: bool = False):
        # 每生成一段文本就往队列里放；stream_end=True 时额外放一个 None 作为结束信号。
        self.queue.put(text)
        if stream_end:
            self.queue.put(None)


def _start_generation_thread(prompt_inputs, runtime_streamer, temperature: float, top_p: float, max_tokens: int) -> None:
    """在后台线程里执行真实模型生成。

    主线程只负责从队列里拿片段并转成 SSE，避免阻塞 FastAPI 响应。
    """

    def _generate():
        model.generate(
            prompt_inputs.input_ids,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            attention_mask=prompt_inputs.attention_mask,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            streamer=runtime_streamer,
        )

    Thread(target=_generate, daemon=True).start()


def generate_stream_response(messages, temperature, top_p, max_tokens, tools=None):
    """处理 `stream=True` 的响应。

    这里和旧实现的关键差异是：
    - 旧实现：把模型吐出来的所有片段都当普通文本 `delta.content`
    - 新实现：先经过 `OpenAIStreamEventAssembler`
      - 普通文本继续走 `delta.content`
      - `<tool_call>...</tool_call>` 会被边生成边翻译成 `delta.tool_calls`
      - 结束时 finish_reason 会区分 `stop` / `tool_calls`
    """

    try:
        ensure_runtime_ready()
        prompt = build_chat_prompt(
            tokenizer=tokenizer,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
        )
        prompt_inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)

        queue: Queue = Queue()
        runtime_streamer = CustomStreamer(tokenizer, queue)
        assembler = OpenAIStreamEventAssembler()

        _start_generation_thread(
            prompt_inputs=prompt_inputs,
            runtime_streamer=runtime_streamer,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        while True:
            text = queue.get()
            if text is None:
                for payload in assembler.finalize():
                    yield json.dumps(payload, ensure_ascii=False)
                break

            for payload in assembler.push_text(text):
                yield json.dumps(payload, ensure_ascii=False)

    except Exception as exc:
        yield json.dumps({"error": str(exc)}, ensure_ascii=False)


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """兼容 OpenAI `/v1/chat/completions`。"""

    try:
        ensure_runtime_ready()
        if request.stream:
            return StreamingResponse(
                (
                    f"data: {chunk}\n\n"
                    for chunk in generate_stream_response(
                        messages=request.messages,
                        temperature=request.temperature,
                        top_p=request.top_p,
                        max_tokens=request.max_tokens,
                        tools=request.tools,
                    )
                ),
                media_type="text/event-stream",
            )

        prompt = build_chat_prompt(
            tokenizer=tokenizer,
            messages=request.messages,
            max_tokens=request.max_tokens,
            tools=request.tools,
        )
        prompt_inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)
        with torch.no_grad():
            generated_ids = model.generate(
                prompt_inputs["input_ids"],
                max_length=prompt_inputs["input_ids"].shape[1] + request.max_tokens,
                do_sample=True,
                attention_mask=prompt_inputs["attention_mask"],
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                top_p=request.top_p,
                temperature=request.temperature,
            )
            answer = tokenizer.decode(
                generated_ids[0][prompt_inputs["input_ids"].shape[1] :],
                skip_special_tokens=True,
            )

        assistant_payload = parse_tool_call_response(answer)
        finish_reason = "tool_calls" if assistant_payload["tool_calls"] else "stop"
        message = {"role": "assistant", "content": assistant_payload["content"]}
        if assistant_payload["tool_calls"]:
            message["tool_calls"] = assistant_payload["tool_calls"]

        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "minimind",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    runtime_defaults = default_runtime_paths(__file__)

    parser = argparse.ArgumentParser(description="Server for MiniMind")
    parser.add_argument(
        "--load_from",
        default=runtime_defaults["load_from"],
        type=str,
        help="模型加载路径（model=原生 torch 权重，其它路径=transformers 格式目录）",
    )
    parser.add_argument("--save_dir", default=runtime_defaults["save_dir"], type=str, help="模型权重目录")
    parser.add_argument(
        "--weight",
        default="full_sft",
        type=str,
        help="权重名称前缀（pretrain, full_sft, dpo, reason, ppo_actor, grpo, spo）",
    )
    parser.add_argument(
        "--lora_weight",
        default="None",
        type=str,
        help="LoRA 权重名称（None 表示不使用，可选：lora_identity, lora_medical）",
    )
    parser.add_argument(
        "--hidden_size",
        default=512,
        type=int,
        help="隐藏层维度（512=Small-26M, 640=MoE-145M, 768=Base-104M）",
    )
    parser.add_argument(
        "--num_hidden_layers",
        default=8,
        type=int,
        help="隐藏层数量（Small/MoE=8, Base=16）",
    )
    parser.add_argument("--max_seq_len", default=8192, type=int, help="最大序列长度")
    parser.add_argument(
        "--use_moe",
        default=0,
        type=int,
        choices=[0, 1],
        help="是否使用 MoE 架构（0=否，1=是）",
    )
    parser.add_argument(
        "--inference_rope_scaling",
        default=False,
        action="store_true",
        help="启用 RoPE 外推（只解决位置编码问题，不等价于重新训练长上下文）",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch is not None and torch.cuda.is_available() else "cpu",
        type=str,
        help="运行设备",
    )

    args = resolve_runtime_args(parser.parse_args(), __file__)
    device = args.device
    model, tokenizer = init_model(args)
    uvicorn.run(app, host="0.0.0.0", port=8998)
