"""金融研究员 Agent：Function Calling 多轮工具调用循环。"""
import asyncio
import json
import re
import uuid
from typing import Any, Optional

from ..tools.registry import TOOLS, call_tool
from .llm import chat

MAX_TOOL_ROUNDS = 8

# Qwen 系模型在标准 OpenAI tools 参数下可能直接输出 <tool_call> 文本而非结构化字段，
# 这里做一层解析兜底（本地 llama.cpp 服务走 GGUF 内置模板时尤其需要）。
_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

SYSTEM_PROMPT = """你是一名严谨的金融行业研究员，服务对象是专业投资研究人员。

工作准则（必须严格遵守）：
1. 一切行情数字、财务数据、新闻事实只能来自工具返回，禁止编造或凭记忆杜撰任何数字、代码与日期。
2. 回答前应主动调用工具收集数据：公司概况、历史行情/技术指标、最新新闻；数据缺失时明确说明"未获取到"，不得猜测。
3. 分析需结构清晰、客观克制，区分"事实"与"研判"，给出多空两面观点。
4. 不做确定性股价预测，不提供具体买卖指令；涉及未来判断时使用概率化、情景化表述。
5. 输出使用简体中文 Markdown；报告末尾必须附上免责声明：
   "本报告由 AI 基于公开数据自动生成，仅供研究参考，不构成任何投资建议。"
6. 引用数据时注明证券代码与数据截止日期。
"""

RESEARCH_TASK_TEMPLATE = """请对 {market_label}【{symbol}】生成一份个股研究简报。

要求：
1. 依次调用工具获取：公司概况、近 120 个交易日行情对应的技术指标、最新 5 条新闻；
2. 输出 MarkDown，固定包含以下小节：
   ## 一、公司概况
   ## 二、行情与技术面（引用最新收盘价、均线、RSI、MACD、波动率、最大回撤等）
   ## 三、消息面（基于新闻客观归纳，不得夸大）
   ## 四、综合研判（多空因素分列，情景化表述）
   ## 五、风险提示
   末尾附规定的免责声明；
3. 每个关键数字后用括号注明数据截止日期。"""

_MARKET_LABEL = {"cn": "A 股", "us": "美股"}


def build_research_task(symbol: str, market: str) -> str:
    return RESEARCH_TASK_TEMPLATE.format(
        symbol=symbol, market_label=_MARKET_LABEL.get(market, market)
    )


async def run_agent(task: str) -> dict[str, Any]:
    """执行一次完整的 Agent 任务（单轮任务入口）。"""
    return await run_agent_messages(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
    )


async def run_agent_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """执行 Agent 循环，messages 为完整的 OpenAI 风格消息列表（支持多轮上下文）。

    返回: {"answer": str, "steps": [工具调用轨迹], "usage": dict|None}
    """
    if not any(m.get("role") == "system" for m in messages):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    steps: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ROUNDS):
        resp = await chat(messages, tools=TOOLS)
        msg = resp.choices[0].message

        # 统一为 dict 结构，兼容 litellm 对象与文本解析结果
        tool_calls = [
            tc.model_dump() if hasattr(tc, "model_dump") else tc
            for tc in (msg.tool_calls or [])
        ]
        if not tool_calls and msg.content and "<tool_call>" in msg.content:
            tool_calls = _parse_tool_calls_from_content(msg.content)

        if not tool_calls:
            return {
                "answer": msg.content or "",
                "steps": steps,
                "usage": _usage_to_dict(getattr(resp, "usage", None)),
            }

        # 回传 assistant 的工具调用请求
        if msg.tool_calls:
            messages.append(msg.model_dump(exclude_none=True))
        else:
            # 文本形式的 tool_call 按原文回传，模型模板可识别
            messages.append({"role": "assistant", "content": msg.content or ""})

        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}

            # 数据工具均为同步阻塞 IO，放到线程池执行，避免卡住事件循环
            result = await asyncio.to_thread(call_tool, tc["function"]["name"], args)
            steps.append({"tool": tc["function"]["name"], "arguments": args})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["function"]["name"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    return {
        "answer": "已达到最大工具调用轮数仍未完成，请缩小分析范围后重试。",
        "steps": steps,
        "usage": None,
    }


def _parse_tool_calls_from_content(content: str) -> list[dict[str, Any]]:
    """从模型文本输出中解析 <tool_call>{"name":..., "arguments":...}</tool_call>。"""
    parsed: list[dict[str, Any]] = []
    for m in _TOOL_CALL_RE.finditer(content):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name")
        if not name:
            continue
        args = obj.get("arguments", {})
        parsed.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args if isinstance(args, str) else json.dumps(args),
                },
            }
        )
    return parsed


def _usage_to_dict(usage: Optional[Any]) -> Optional[dict[str, int]]:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        d = usage.model_dump()
    elif isinstance(usage, dict):
        d = usage
    else:
        return None
    return {
        "prompt_tokens": int(d.get("prompt_tokens", 0)),
        "completion_tokens": int(d.get("completion_tokens", 0)),
        "total_tokens": int(d.get("total_tokens", 0)),
    }
