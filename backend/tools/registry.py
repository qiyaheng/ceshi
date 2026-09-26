"""Function Calling 工具注册中心：OpenAI 工具 schema + 同步分发。"""
from typing import Any

from .indicators import compute_indicators
from .market_data import get_latest_news, get_price_history, get_stock_profile

_MARKET_ENUM = ["cn", "us"]

_SYMBOL_PROP = {
    "type": "string",
    "description": "证券代码：A 股为 6 位数字（如 600519、000001）；美股为字母代码（如 AAPL、TSLA）",
}
_MARKET_PROP = {
    "type": "string",
    "enum": _MARKET_ENUM,
    "description": "市场：cn=A股（沪深京），us=美股。不传则根据代码自动判断",
}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_profile",
            "description": "获取上市公司基本概况：名称、行业、市值、上市地等。",
            "parameters": {
                "type": "object",
                "properties": {"symbol": _SYMBOL_PROP, "market": _MARKET_PROP},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": (
                "获取日 K 历史行情（前复权），含开高低收、成交量与涨跌幅；"
                "同时返回起止日期。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": _SYMBOL_PROP,
                    "market": _MARKET_PROP,
                    "days": {
                        "type": "integer",
                        "description": "需要的交易日数量，20-250，默认 120",
                        "default": 120,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": (
                "获取技术面与风险指标快照：均线(MA5/10/20/60)、RSI14、MACD、"
                "近5/20/60日涨跌幅、20日年化波动率、窗口内最大回撤、区间高低点，"
                "并附带确定性文字解读。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": _SYMBOL_PROP,
                    "market": _MARKET_PROP,
                    "days": {
                        "type": "integer",
                        "description": "计算窗口的交易日数量，默认 120",
                        "default": 120,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_news",
            "description": "获取与该证券相关的最新新闻资讯（标题、时间、来源、链接）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": _SYMBOL_PROP,
                    "market": _MARKET_PROP,
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，1-10，默认 5",
                        "default": 5,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
]

_DISPATCH = {
    "get_stock_profile": lambda a: get_stock_profile(a["symbol"], a.get("market")),
    "get_price_history": lambda a: get_price_history(
        a["symbol"], a.get("market"), a.get("days", 120)
    ),
    "get_technical_indicators": lambda a: compute_indicators(
        a["symbol"], a.get("market"), a.get("days", 120)
    ),
    "get_latest_news": lambda a: get_latest_news(
        a["symbol"], a.get("market"), a.get("limit", 5)
    ),
}

TOOL_NAMES = list(_DISPATCH.keys())


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = _DISPATCH.get(name)
    if handler is None:
        return {"error": f"未知工具: {name}，可选: {TOOL_NAMES}"}
    if "symbol" not in arguments or not str(arguments.get("symbol", "")).strip():
        return {"error": "缺少必填参数 symbol（证券代码）"}
    try:
        return handler(arguments)
    except Exception as e:
        return {"error": f"工具 {name} 执行异常: {type(e).__name__}: {e}"}
