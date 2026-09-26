"""请求/响应模型（Pydantic v2）。"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Market = Literal["cn", "us"]


class ResearchRequest(BaseModel):
    symbol: str = Field(..., description="证券代码：A 股 6 位数字（600519）或美股代码（AAPL）")
    market: Optional[Market] = Field(None, description="不传则按代码自动识别")


class AgentChatRequest(BaseModel):
    message: str = Field(..., description="自然语言任务，如：分析一下贵州茅台近期的技术面")


class ResearchResponse(BaseModel):
    symbol: str
    market: Market
    report_markdown: str
    steps: list[dict[str, Any]]
    usage: Optional[dict[str, int]] = None


class ChatCompletionRequest(BaseModel):
    """最小化的 OpenAI 兼容请求；只取对接常用字段。"""

    model: str = "fin-researcher"
    messages: list[dict[str, Any]]
    temperature: float = 0.3
    stream: bool = False
