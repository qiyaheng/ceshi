"""Agent 循环离线冒烟测试：用假 LLM 响应驱动真实工具链，无需 API Key。

运行：.venv\\Scripts\\python.exe scripts\\smoke_test_agent.py
"""
import asyncio
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core import agent
from backend.reports.generator import build_equity_report
from backend.tools.market_data import get_stock_profile


class FakeFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: dict):
        self.id = call_id
        self.type = "function"
        self.function = FakeFunction(name, json.dumps(arguments))


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in self.tool_calls
            ]
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        return data


class FakeResponse:
    def __init__(self, message):
        self.choices = [types.SimpleNamespace(message=message)]
        self.usage = None


async def main():
    state = {"round": 0}

    async def fake_chat(messages, tools=None, temperature=0.3):
        state["round"] += 1
        if state["round"] == 1:
            return FakeResponse(
                FakeMessage(
                    tool_calls=[
                        FakeToolCall("call_1", "get_stock_profile", {"symbol": "600519"}),
                        FakeToolCall(
                            "call_2", "get_technical_indicators", {"symbol": "600519", "days": 90}
                        ),
                    ]
                )
            )
        return FakeResponse(
            FakeMessage(
                content=(
                    "## 一、公司概况\n贵州茅台（600519）为 A 股白酒龙头。\n\n"
                    "## 二、行情与技术面\n（基于工具返回数据的示例结论）\n\n"
                    "## 三、消息面\n近期无重大异常公告。\n\n"
                    "## 四、综合研判\n多空因素相对均衡。\n\n"
                    "## 五、风险提示\n消费复苏不及预期。\n\n"
                    "本报告由 AI 基于公开数据自动生成，仅供研究参考，不构成任何投资建议。"
                )
            )
        )

    agent.chat = fake_chat
    result = await agent.run_agent(agent.build_research_task("600519", "cn"))

    print("=== 工具调用轨迹 ===")
    for s in result["steps"]:
        print("-", s["tool"], s["arguments"])
    assert len(result["steps"]) == 2, "应发生 2 次工具调用"
    assert "贵州茅台" in result["answer"]

    profile = get_stock_profile("600519", "cn")
    report = build_equity_report("600519", "cn", result["answer"], result["steps"], profile)
    print("\n=== 研报前 20 行 ===")
    print("\n".join(report.splitlines()[:20]))
    assert "免责声明" in report
    print("\nSMOKE_TEST_OK")


if __name__ == "__main__":
    asyncio.run(main())
