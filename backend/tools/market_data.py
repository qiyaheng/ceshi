"""行情与资讯数据工具。

数据源策略（主备自动切换，规避单一接口被限流/封锁）：
- 行情/概况主源：腾讯财经行情接口（httpx 直连，沪深京 + 美股均支持，A 股提供前复权）
- A 股备源：AkShare（东方财富）；美股备源：yfinance
- 新闻：A 股 AkShare（东财）/ 美股 yfinance，失败时返回 error，不阻塞主流程

所有对外返回均为 JSON 可序列化的原生类型（dict/list/float/str），
异常被捕获并包装为 {"error": ...}，交由 Agent 决定下一步。
"""
import datetime as dt
import re
from typing import Any, Optional

import httpx
import pandas as pd

from .cache import ttl_get

CACHE_TTL_QUOTE = 600    # 行情/概况缓存 10 分钟
CACHE_TTL_NEWS = 300    # 新闻缓存 5 分钟
CACHE_TTL_SYMBOL = 86400  # 美股代码到交易所后缀的解析结果缓存 1 天

_HTTP = httpx.Client(
    timeout=httpx.Timeout(15.0, connect=10.0),
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": "https://gu.qq.com/",
    },
    follow_redirects=True,
)


# ---------------------------------------------------------------- 市场识别

def detect_market(symbol: str) -> str:
    """根据代码格式判断市场：6 位数字为 A 股，其余按美股处理。"""
    s = symbol.strip()
    if re.fullmatch(r"\d{6}", s):
        return "cn"
    if re.fullmatch(r"[A-Za-z.\-]{1,10}", s):
        return "us"
    raise ValueError(f"无法识别证券代码: {symbol!r}（A 股为 6 位数字，美股为字母代码如 AAPL）")


def normalize_symbol(symbol: str, market: Optional[str] = None) -> tuple[str, str]:
    market = market or detect_market(symbol)
    if market not in ("cn", "us"):
        raise ValueError(f"market 仅支持 cn / us，收到: {market!r}")
    symbol = symbol.strip()
    if market == "us":
        symbol = symbol.upper()
    return symbol, market


# ---------------------------------------------------------------- 腾讯行情（主源）

def _tx_cn_symbol(symbol: str) -> str:
    """A 股代码加交易所前缀：6/9 开头沪市（920 为北交所新号段），4/8 北交所，其余深市。"""
    if symbol.startswith(("6", "9")) and not symbol.startswith("920"):
        return f"sh{symbol}"
    if symbol.startswith(("4", "8")) or symbol.startswith("920"):
        return f"bj{symbol}"
    return f"sz{symbol}"


def _tx_resolve_us(symbol: str) -> str:
    """将美股代码解析为腾讯行情符号，如 AAPL -> usAAPL.OQ、JPM -> usJPM.N。"""
    def _resolve() -> str:
        r = _HTTP.get("https://smartbox.gtimg.cn/s3/", params={"q": symbol, "t": "us"})
        text = r.content.decode("gbk", errors="ignore")
        m = re.search(r'v_hint="([^"]+)"', text)
        if m:
            first = m.group(1).split("^")[0]
            parts = first.split("~")
            if len(parts) >= 2 and parts[1]:
                return "us" + parts[1].upper()
        # 兜底：先试纳斯达克，再试纽交所
        return f"us{symbol}.OQ"

    resolved = ttl_get(f"tx_resolve:{symbol}", CACHE_TTL_SYMBOL, _resolve)

    # 兜底结果需用真实行情验证；OQ 不通则尝试 N
    if resolved.endswith(".OQ"):
        try:
            _tx_kline_raw(resolved, 5)
        except Exception:
            alt = f"us{symbol}.N"
            try:
                _tx_kline_raw(alt, 5)
                resolved = alt
            except Exception:
                pass
    return resolved


def _tx_kline_raw(tx_symbol: str, days: int) -> list[list[Any]]:
    end = dt.date.today()
    start = end - dt.timedelta(days=int(days * 1.6) + 15)
    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    if tx_symbol.startswith("us"):
        url = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline"
        param = f"{tx_symbol},day,{start_s},{end_s},{max(days, 60)}"
        keys = ("day",)
    else:
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        param = f"{tx_symbol},day,{start_s},{end_s},640,qfq"
        keys = ("qfqday", "day")

    r = _HTTP.get(url, params={"param": param})
    payload = r.json()
    node = payload.get("data", {}).get(tx_symbol) or {}
    for key in keys:
        rows = node.get(key)
        if rows:
            return rows
    raise RuntimeError(f"腾讯行情未返回 {tx_symbol} 的 K 线数据")


def _tx_history(symbol: str, market: str, days: int) -> tuple[str, list[dict[str, Any]]]:
    if market == "cn":
        tx_symbol = _tx_cn_symbol(symbol)
        volume_unit = "lots"  # 手
    else:
        tx_symbol = _tx_resolve_us(symbol)
        volume_unit = "shares"

    rows = _tx_kline_raw(tx_symbol, days)[-days:]
    bars: list[dict[str, Any]] = []
    prev_close: Optional[float] = None
    for row in rows:
        date, open_, close, high, low, volume = row[:6]
        close_f = float(close)
        change_pct = (
            round((close_f / prev_close - 1.0) * 100.0, 2)
            if prev_close
            else None
        )
        bars.append(
            {
                "date": str(date),
                "open": round(float(open_), 3),
                "close": round(close_f, 3),
                "high": round(float(high), 3),
                "low": round(float(low), 3),
                "volume": float(volume),
                "change_pct": change_pct,
            }
        )
        prev_close = close_f
    return volume_unit, bars


def _tx_quote(tx_symbol: str) -> list[str]:
    r = _HTTP.get("https://qt.gtimg.cn/q=" + tx_symbol)
    text = r.content.decode("gbk", errors="ignore")
    if "none_match" in text or "=\"" not in text:
        raise RuntimeError(f"腾讯行情无此标的: {tx_symbol}")
    body = text[text.find("=\"") + 2: text.rfind("\"")]
    return body.split("~")


def _f(p: list[str], idx: int) -> Optional[float]:
    try:
        v = p[idx]
        return float(v) if v not in ("", None) else None
    except (IndexError, ValueError, TypeError):
        return None


def _tx_cn_profile(symbol: str) -> dict[str, Any]:
    p = _tx_quote(_tx_cn_symbol(symbol))
    total_mcap = _f(p, 45)   # 总市值（亿元）
    float_mcap = _f(p, 44)   # 流通市值（亿元）
    return {
        "symbol": symbol,
        "market": "cn",
        "currency": "CNY",
        "name": p[1] if len(p) > 1 else None,
        "industry": None,  # 腾讯行情不含行业；东财备源可用时补充
        "total_market_cap_cny_100m": total_mcap,
        "float_market_cap_cny_100m": float_mcap,
        "pe_ttm": _f(p, 39),
        "pb": _f(p, 46),
        "turnover_rate_pct": _f(p, 38),
        "last_price": _f(p, 3),
        "as_of": p[30] if len(p) > 30 else None,
    }


def _tx_us_profile(symbol: str) -> dict[str, Any]:
    tx_symbol = _tx_resolve_us(symbol)
    # 报价接口使用无交易所后缀的形式（usAAPL），K 线接口才用 usAAPL.OQ
    p = _tx_quote(tx_symbol.split(".")[0])
    total_mcap_yi = _f(p, 45)  # 总市值（亿美元）
    return {
        "symbol": symbol,
        "market": "us",
        "currency": p[35] if len(p) > 35 and p[35] else "USD",
        "name": (p[46] if len(p) > 46 and p[46] else None)
        or (p[1] if len(p) > 1 else None),
        "name_cn": p[1] if len(p) > 1 else None,
        "industry": None,
        "sector": None,
        "exchange": tx_symbol.split(".")[-1] if "." in tx_symbol else None,
        "total_market_cap_usd": round(total_mcap_yi * 1e8, 2) if total_mcap_yi else None,
        "pe_ttm": _f(p, 39),
        "eps": _f(p, 47),
        "week52_high": _f(p, 48),
        "week52_low": _f(p, 49),
        "last_price": _f(p, 3),
        "as_of": p[30] if len(p) > 30 else None,
    }


# ---------------------------------------------------------------- A 股备源（AkShare）

def _cn_history_ak(symbol: str, days: int) -> list[dict[str, Any]]:
    import akshare as ak

    end = dt.date.today()
    start = end - dt.timedelta(days=int(days * 1.6) + 15)
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df is None or df.empty:
        return []
    bars: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        bars.append(
            {
                "date": pd.to_datetime(r["日期"]).strftime("%Y-%m-%d"),
                "open": round(float(r["开盘"]), 3),
                "close": round(float(r["收盘"]), 3),
                "high": round(float(r["最高"]), 3),
                "low": round(float(r["最低"]), 3),
                "volume": float(r["成交量"]),
                "change_pct": _safe_float(r.get("涨跌幅")),
            }
        )
    return bars[-days:]


def _cn_profile_ak(symbol: str) -> dict[str, Any]:
    import akshare as ak

    df = ak.stock_individual_info_em(symbol=symbol)
    raw = dict(zip(df["item"].astype(str), df["value"]))

    def _yuan(v: Any) -> Optional[float]:
        f = _safe_float(v)
        return round(f / 1e8, 2) if f is not None else None

    return {
        "symbol": symbol,
        "market": "cn",
        "currency": "CNY",
        "name": _safe_str(raw.get("股票简称")),
        "industry": _safe_str(raw.get("行业")),
        "list_date": _safe_str(raw.get("上市时间")),
        "total_market_cap_cny_100m": _yuan(raw.get("总市值")),
        "float_market_cap_cny_100m": _yuan(raw.get("流通市值")),
        "total_shares": _safe_float(raw.get("总股本")),
        "float_shares": _safe_float(raw.get("流通股")),
    }


def _cn_news(symbol: str, limit: int) -> list[dict[str, Any]]:
    import akshare as ak

    df = ak.stock_news_em(symbol=symbol)
    if df is None or df.empty:
        return []
    out = []
    for _, r in df.head(limit).iterrows():
        ts = r.get("发布时间")
        out.append(
            {
                "title": _safe_str(r.get("新闻标题")),
                "published_at": pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M")
                if pd.notna(ts)
                else None,
                "source": _safe_str(r.get("文章来源")),
                "url": _safe_str(r.get("新闻链接")),
            }
        )
    return out


# ---------------------------------------------------------------- 美股备源（yfinance）

def _us_ticker(symbol: str):
    import yfinance as yf

    return yf.Ticker(symbol)


def _us_history_yf(symbol: str, days: int) -> list[dict[str, Any]]:
    tk = _us_ticker(symbol)
    period = "1y" if days > 180 else f"{days + 30}d"
    df = tk.history(period=period, auto_adjust=True)
    if df is None or df.empty:
        return []
    df = df.sort_index()
    closes = df["Close"].astype(float)
    prev = closes.shift(1)
    change_pct = (closes / prev - 1.0) * 100.0
    bars: list[dict[str, Any]] = []
    for idx, (ts, r) in enumerate(df.iterrows()):
        bars.append(
            {
                "date": pd.Timestamp(ts).strftime("%Y-%m-%d"),
                "open": round(float(r["Open"]), 3),
                "close": round(float(r["Close"]), 3),
                "high": round(float(r["High"]), 3),
                "low": round(float(r["Low"]), 3),
                "volume": float(r["Volume"]),
                "change_pct": round(change_pct.iloc[idx], 2)
                if pd.notna(change_pct.iloc[idx])
                else None,
            }
        )
    return bars[-days:]


def _us_profile_yf(symbol: str) -> dict[str, Any]:
    tk = _us_ticker(symbol)
    try:
        info = tk.info or {}
    except Exception:
        info = {}
    market_cap = _safe_float(info.get("marketCap"))
    return {
        "symbol": symbol,
        "market": "us",
        "currency": _safe_str(info.get("currency")) or "USD",
        "name": _safe_str(info.get("longName")) or _safe_str(info.get("shortName")),
        "name_cn": None,
        "industry": _safe_str(info.get("industry")),
        "sector": _safe_str(info.get("sector")),
        "exchange": _safe_str(info.get("fullExchangeName")) or _safe_str(info.get("exchange")),
        "total_market_cap_usd": round(market_cap, 2) if market_cap is not None else None,
        "pe_ttm": _safe_float(info.get("trailingPE")),
        "week52_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        "week52_low": _safe_float(info.get("fiftyTwoWeekLow")),
        "website": _safe_str(info.get("website")),
        "summary": _safe_str(info.get("longBusinessSummary")),
    }


def _us_news(symbol: str, limit: int) -> list[dict[str, Any]]:
    tk = _us_ticker(symbol)
    try:
        raw_news = tk.news or []
    except Exception:
        return []

    out = []
    for item in raw_news[:limit]:
        # yfinance 新版结构 {"content": {"title", "pubDate", ...}}，兼容旧版平铺结构
        content = item.get("content", item) if isinstance(item, dict) else {}
        title = _safe_str(content.get("title"))
        if not title:
            continue
        published = content.get("pubDate") or content.get("providerPublishTime")
        if isinstance(published, (int, float)):
            published_at = dt.datetime.fromtimestamp(published).strftime("%Y-%m-%d %H:%M")
        elif published:
            published_at = _safe_str(published)[:16].replace("T", " ")
        else:
            published_at = None
        url = content.get("canonicalUrl")
        if isinstance(url, dict):
            url = url.get("url")
        provider = content.get("provider")
        if isinstance(provider, dict):
            provider = provider.get("displayName")
        out.append(
            {
                "title": title,
                "published_at": published_at,
                "source": _safe_str(provider),
                "url": _safe_str(url),
            }
        )
    return out


# ---------------------------------------------------------------- 公共入口

def get_price_history(symbol: str, market: Optional[str] = None, days: int = 120) -> dict[str, Any]:
    symbol, market = normalize_symbol(symbol, market)
    days = max(20, min(int(days), 250))
    errors: list[str] = []
    try:
        if market == "cn":
            volume_unit, bars = ttl_get(
                f"hist:cn:{symbol}:{days}", CACHE_TTL_QUOTE,
                lambda: _tx_history(symbol, "cn", days),
            )
        else:
            volume_unit, bars = ttl_get(
                f"hist:us:{symbol}:{days}", CACHE_TTL_QUOTE,
                lambda: _tx_history(symbol, "us", days),
            )
        if bars:
            return {
                "symbol": symbol,
                "market": market,
                "currency": "CNY" if market == "cn" else "USD",
                "volume_unit": volume_unit,
                "days": len(bars),
                "start_date": bars[0]["date"],
                "end_date": bars[-1]["date"],
                "bars": bars,
            }
    except Exception as e:
        errors.append(f"腾讯行情: {type(e).__name__}: {e}")

    # 备源
    try:
        bars = (
            ttl_get(f"ak_hist:{symbol}:{days}", CACHE_TTL_QUOTE,
                    lambda: _cn_history_ak(symbol, days))
            if market == "cn"
            else ttl_get(f"yf_hist:{symbol}:{days}", CACHE_TTL_QUOTE,
                         lambda: _us_history_yf(symbol, days))
        )
        if bars:
            return {
                "symbol": symbol,
                "market": market,
                "currency": "CNY" if market == "cn" else "USD",
                "volume_unit": "lots" if market == "cn" else "shares",
                "source": "akshare" if market == "cn" else "yfinance",
                "days": len(bars),
                "start_date": bars[0]["date"],
                "end_date": bars[-1]["date"],
                "bars": bars,
            }
    except Exception as e:
        errors.append(f"备用源: {type(e).__name__}: {e}")

    return {"error": f"获取 {symbol} 行情失败，所有数据源均不可用：{'；'.join(errors)}"}


def get_stock_profile(symbol: str, market: Optional[str] = None) -> dict[str, Any]:
    symbol, market = normalize_symbol(symbol, market)
    try:
        if market == "cn":
            return ttl_get(f"profile:cn:{symbol}", CACHE_TTL_QUOTE,
                           lambda: _tx_cn_profile(symbol))
        return ttl_get(f"profile:us:{symbol}", CACHE_TTL_QUOTE,
                       lambda: _tx_us_profile(symbol))
    except Exception:
        try:
            if market == "cn":
                return _cn_profile_ak(symbol)
            return _us_profile_yf(symbol)
        except Exception as e:
            return {"error": f"获取 {symbol} 公司概况失败: {type(e).__name__}: {e}"}


def get_latest_news(symbol: str, market: Optional[str] = None, limit: int = 5) -> dict[str, Any]:
    symbol, market = normalize_symbol(symbol, market)
    limit = max(1, min(int(limit), 10))
    try:
        if market == "cn":
            news = ttl_get(f"news:cn:{symbol}:{limit}", CACHE_TTL_NEWS,
                           lambda: _cn_news(symbol, limit))
        else:
            news = ttl_get(f"news:us:{symbol}:{limit}", CACHE_TTL_NEWS,
                           lambda: _us_news(symbol, limit))
        return {"symbol": symbol, "market": market, "count": len(news), "news": news}
    except Exception as e:
        return {"error": f"获取 {symbol} 新闻失败: {type(e).__name__}: {e}"}


# ---------------------------------------------------------------- 小工具

def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None
