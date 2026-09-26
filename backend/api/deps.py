"""API 依赖：Bearer Token 鉴权（SERVICE_API_KEY 为空时不鉴权，仅限本地）。"""
import hmac

from fastapi import Header, HTTPException, status

from ..config import get_settings


async def verify_api_key(authorization: str = Header(default="")) -> None:
    expected = get_settings().service_api_key
    if not expected:
        return
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或缺失的 API Key（请使用 Authorization: Bearer <key>）",
        )
