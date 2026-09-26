"""FastAPI 入口。

启动：在项目根目录执行
    uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_chat, routes_research
from .config import get_settings
from .core import llm

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="金融行业研究员 Agent：市场调研 + 报告生成（A股 / 美股）",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_research.router)
app.include_router(routes_chat.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "llm_configured": "yes" if settings.has_any_llm_key() else "no",
    }
