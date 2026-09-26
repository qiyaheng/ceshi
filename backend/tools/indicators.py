"""技术指标与风险统计（纯 pandas/numpy 实现，避免 TA-Lib 的 C 依赖）。"""
import math
from typing import Any, Optional

import pandas as pd

from .market_data import get_price_history


def _round(v: Optional[float], ndigits: int = 2) -> Optional[float]:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), ndigits)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder 平滑
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return 100 - 100 / (1 + rs)


def _max_drawdown(close: pd.Series) -> float:
    cummax = close.cummax()
    drawdown = close / cummax - 1.0
    return float(drawdown.min()) * 100.0


def compute_indicators(symbol: str, market: Optional[str] = None, days: int = 120) -> dict[str, Any]:
    data = get_price_history(symbol, market, days=days)
    if "error" in data:
        return data

    df = pd.DataFrame(data["bars"])
    close = df["close"].astype(float)
    n = len(df)

    ma = {}
    for w in (5, 10, 20, 60):
        ma[f"ma{w}"] = _round(close.rolling(w).mean().iloc[-1]) if n >= w else None

    rsi14 = _rsi(close).iloc[-1] if n >= 15 else None

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_hist = (dif - dea) * 2

    def _ret(window: int) -> Optional[float]:
        if n <= window:
            return None
        return _round((close.iloc[-1] / close.iloc[-1 - window] - 1.0) * 100.0)

    daily_ret = close.pct_change().dropna()
    ann_days = 244 if data["market"] == "cn" else 252
    vol20 = daily_ret.tail(20)
    volatility = (
        float(vol20.std()) * math.sqrt(ann_days) * 100.0 if len(vol20) >= 5 else None
    )

    last = df.iloc[-1]
    snapshot = {
        "symbol": data["symbol"],
        "market": data["market"],
        "currency": data["currency"],
        "as_of": last["date"],
        "trading_days": n,
        "last_close": _round(close.iloc[-1]),
        "change_pct_1d": _round(last.get("change_pct")),
        "return_pct_5d": _ret(5),
        "return_pct_20d": _ret(20),
        "return_pct_60d": _ret(60),
        "ma5": ma["ma5"],
        "ma10": ma["ma10"],
        "ma20": ma["ma20"],
        "ma60": ma["ma60"],
        "rsi14": _round(rsi14),
        "macd_dif": _round(dif.iloc[-1], 3),
        "macd_dea": _round(dea.iloc[-1], 3),
        "macd_hist": _round(macd_hist.iloc[-1], 3),
        "volatility_annualized_pct_20d": _round(volatility),
        "max_drawdown_pct_in_window": _round(_max_drawdown(close)),
        "window_high": _round(df["high"].astype(float).max()),
        "window_low": _round(df["low"].astype(float).min()),
    }
    snapshot["summary"] = _build_summary(snapshot)
    return snapshot


def _build_summary(s: dict[str, Any]) -> str:
    """生成确定性的指标解读文本（不依赖 LLM，避免重复造轮子）。"""
    parts = []

    last, ma20, ma60 = s["last_close"], s["ma20"], s["ma60"]
    if last and ma20:
        parts.append(f"收盘价位于20日均线{'上方' if last >= ma20 else '下方'}")
    if last and ma60:
        parts.append(f"位于60日均线{'上方' if last >= ma60 else '下方'}")

    rsi = s["rsi14"]
    if rsi is not None:
        if rsi >= 70:
            zone = "超买区间"
        elif rsi <= 30:
            zone = "超卖区间"
        else:
            zone = "中性区间"
        parts.append(f"RSI14={rsi}（{zone}）")

    if s["macd_hist"] is not None:
        parts.append(f"MACD柱{'为正，短期动能偏强' if s['macd_hist'] > 0 else '为负，短期动能偏弱'}")

    if s["volatility_annualized_pct_20d"] is not None:
        parts.append(f"近20日年化波动率约{s['volatility_annualized_pct_20d']}%")
    if s["max_drawdown_pct_in_window"] is not None:
        parts.append(f"窗口内最大回撤{s['max_drawdown_pct_in_window']}%")

    return "；".join(parts) + "。" if parts else ""
