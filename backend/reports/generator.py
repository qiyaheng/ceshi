"""研报组装：在 Agent 产出的正文外补充标题、数据溯源与免责声明。"""
import datetime as dt
from typing import Any

_MARKET_LABEL = {"cn": "A 股", "us": "美股"}
_CURRENCY = {"cn": "人民币", "us": "美元"}


def build_equity_report(
    symbol: str,
    market: str,
    answer: str,
    steps: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
) -> str:
    name = (profile or {}).get("name") if profile and "error" not in profile else None
    title_name = f"{name}（{symbol}）" if name else symbol
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# {_MARKET_LABEL.get(market, market)}{title_name} 研究简报",
        "",
        f"> 生成时间：{now}　|　市场：{_MARKET_LABEL.get(market, market)}　|　计价货币：{_CURRENCY.get(market, '-')}",
        "> 数据来源：公开市场行情接口与公开新闻，经 AI 自动采集与分析",
        "",
        "---",
        "",
        answer.strip(),
        "",
        "---",
        "",
        "## 附录：本次分析的数据采集轨迹",
        "",
    ]
    if steps:
        for i, step in enumerate(steps, 1):
            args = step.get("arguments", {})
            args_text = ", ".join(f"{k}={v}" for k, v in args.items())
            lines.append(f"{i}. `{step.get('tool')}`（{args_text}）")
    else:
        lines.append("- 本次未发生工具调用。")
    lines.extend(
        [
            "",
            "---",
            "",
            "**风险提示与免责声明**：本报告由 AI 基于公开数据自动生成，可能存在数据延迟、缺失或分析偏差，",
            "仅供研究参考，不构成任何投资建议。市场有风险，投资需谨慎。",
        ]
    )
    return "\n".join(lines)
