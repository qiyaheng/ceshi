"""对话类接口：

- POST /v1/agent/chat       便捷对话接口（单轮 message）
- POST /v1/chat/completions 最小化 OpenAI 兼容接口，便于第三方零改造接入
"""
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core.agent import run_agent, run_agent_messages
from ..core import llm
from ..schemas.models import AgentChatRequest, ChatCompletionRequest
from .deps import verify_api_key

router = APIRouter(tags=["chat"], dependencies=[Depends(verify_api_key)])


@router.post("/v1/agent/chat")
async def agent_chat(req: AgentChatRequest) -> dict[str, Any]:
    if llm.router is None:
        raise HTTPException(status_code=503, detail="模型渠道未配置，请先在 .env 中填写 API Key")
    result = await run_agent(req.message)
    return {
        "answer": result["answer"],
        "steps": result["steps"],
        "usage": result["usage"],
    }


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
    """OpenAI Chat Completions 兼容（非流式）。

    第三方系统可把本服务当作一个自带金融工具的模型直接接入，
    最后一条 user message 作为任务输入。
    """
    if llm.router is None:
        raise HTTPException(status_code=503, detail="模型渠道未配置，请先在 .env 中填写 API Key")
    if req.stream:
        raise HTTPException(status_code=400, detail="Phase 0 暂未开放 stream=true")

    user_messages = [m for m in req.messages if m.get("role") == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="messages 中至少包含一条 role=user 消息")
    if not str(user_messages[-1].get("content") or "").strip():
        raise HTTPException(status_code=400, detail="最后一条 user 消息 content 为空")

    # 保留第三方传入的完整多轮上下文，system 准则由 Agent 层自动注入
    result = await run_agent_messages(req.messages)
    usage = result["usage"] or {}
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["answer"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
