"""金融行业专属接口：一键生成个股研究简报。"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from ..core.agent import build_research_task, run_agent
from ..core import llm
from ..reports.generator import build_equity_report
from ..schemas.models import ResearchRequest, ResearchResponse
from ..tools.market_data import detect_market, get_stock_profile
from .deps import verify_api_key

router = APIRouter(prefix="/v1/research", tags=["research"], dependencies=[Depends(verify_api_key)])


@router.post("/equity-report", response_model=ResearchResponse)
async def equity_report(req: ResearchRequest) -> ResearchResponse:
    if llm.router is None:
        raise HTTPException(
            status_code=503,
            detail="模型渠道未配置：请复制 .env.example 为 .env 并填写至少一个 API Key",
        )

    try:
        symbol, market = req.symbol.strip(), (req.market or detect_market(req.symbol))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    task = build_research_task(symbol, market)
    result = await run_agent(task)

    # 概况单独取一次用于报告标题；失败不阻塞主流程
    profile = await asyncio.to_thread(get_stock_profile, symbol, market)
    if "error" in profile:
        profile = None

    report_md = build_equity_report(
        symbol=symbol,
        market=market,
        answer=result["answer"],
        steps=result["steps"],
        profile=profile,
    )
    return ResearchResponse(
        symbol=symbol,
        market=market,
        report_markdown=report_md,
        steps=result["steps"],
        usage=result["usage"],
    )
