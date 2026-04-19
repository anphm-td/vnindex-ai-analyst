"""
VNINDEX AI Analyst - Technical Agent
Tính toán RSI, MACD, ATR, MA và Market Breadth sử dụng TA-Lib.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

import config
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# Lazy-load TA-Lib (hay gặp lỗi cài đặt)
_talib = None


def _get_talib():
    global _talib
    if _talib is not None:
        return _talib
    try:
        import talib
        _talib = talib
        logger.info("TA-Lib loaded successfully.")
    except ImportError:
        logger.warning("TA-Lib not installed. Using manual calculations.")
        _talib = "fallback"
    return _talib


class TechnicalAgent:
    """Agent tính toán chỉ báo kỹ thuật và Market Breadth."""

    def __init__(self):
        self.db = DatabaseManager()

    def run(self, symbols: list[str] = None) -> dict:
        logger.info("📊 Technical Agent: Starting analysis...")

        if not symbols:
            tickers = self.db.get_all_tickers(exchange="HOSE")
            symbols = [t["symbol"] for t in tickers]

        results = {}
        for symbol in symbols:
            try:
                indicators = self._compute_indicators(symbol)
                if indicators:
                    results[symbol] = indicators
                    # Cập nhật DB
                    self.db.update_technical_indicators(
                        symbol=symbol,
                        date=indicators.get("date", datetime.now().strftime("%Y-%m-%d")),
                        rsi_14=indicators.get("rsi_14"),
                        macd=indicators.get("macd"),
                        macd_signal=indicators.get("macd_signal"),
                        atr_14=indicators.get("atr_14"),
                        ma_20=indicators.get("ma_20"),
                    )
            except Exception as e:
                logger.error(f"  {symbol}: {e}")

        # Market Breadth
        breadth = self._compute_market_breadth()

        result = {
            "indicators": results,
            "market_breadth": breadth,
            "symbols_analyzed": len(results),
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(f"📊 Technical Agent: Done. {len(results)} symbols analyzed.")
        return result

    def _compute_indicators(self, symbol: str) -> Optional[dict]:
        prices = self.db.get_recent_prices(symbol, limit=config.TA_LOOKBACK_SESSIONS)
        if len(prices) < 26:  # Cần ít nhất 26 phiên cho MACD
            return None

        # Sắp xếp theo thời gian tăng dần
        prices = list(reversed(prices))
        close = np.array([p["close"] for p in prices], dtype=float)
        high = np.array([p["high"] for p in prices], dtype=float)
        low = np.array([p["low"] for p in prices], dtype=float)

        talib = _get_talib()

        if talib != "fallback" and talib is not None:
            rsi = talib.RSI(close, timeperiod=config.TA_RSI_PERIOD)
            macd_val, macd_sig, _ = talib.MACD(
                close, fastperiod=config.TA_MACD_FAST,
                slowperiod=config.TA_MACD_SLOW,
                signalperiod=config.TA_MACD_SIGNAL
            )
            atr = talib.ATR(high, low, close, timeperiod=config.TA_ATR_PERIOD)
            ma = talib.SMA(close, timeperiod=config.TA_MA_PERIOD)
        else:
            rsi = self._manual_rsi(close, config.TA_RSI_PERIOD)
            macd_val, macd_sig = self._manual_macd(close)
            atr = self._manual_atr(high, low, close, config.TA_ATR_PERIOD)
            ma = self._manual_sma(close, config.TA_MA_PERIOD)

        result = {
            "symbol": symbol,
            "date": prices[-1]["date"],
            "close": float(close[-1]),
            "rsi_14": round(float(rsi[-1]), 2) if not np.isnan(rsi[-1]) else None,
            "macd": round(float(macd_val[-1]), 4) if not np.isnan(macd_val[-1]) else None,
            "macd_signal": round(float(macd_sig[-1]), 4) if not np.isnan(macd_sig[-1]) else None,
            "atr_14": round(float(atr[-1]), 2) if not np.isnan(atr[-1]) else None,
            "ma_20": round(float(ma[-1]), 2) if not np.isnan(ma[-1]) else None,
            "above_ma20": bool(close[-1] > ma[-1]) if not np.isnan(ma[-1]) else None,
            "rsi_signal": self._rsi_signal(float(rsi[-1])) if not np.isnan(rsi[-1]) else "N/A",
            "macd_signal_type": self._macd_signal_type(macd_val, macd_sig),
        }
        
        # Thêm dự báo ML
        ml_res = self._predict_next_close(close)
        result.update(ml_res)
        
        return result

    def _predict_next_close(self, close: np.ndarray) -> dict:
        """Dự báo giá đóng cửa phiên tiếp theo bằng Machine Learning."""
        try:
            from sklearn.linear_model import LinearRegression
            if len(close) < 20:
                return {"ml_pred": None, "ml_trend": "N/A"}
                
            df = pd.DataFrame({"close": close})
            df["lag1"] = df["close"].shift(1)
            df["lag2"] = df["close"].shift(2)
            df["lag3"] = df["close"].shift(3)
            df["target"] = df["close"].shift(-1)
            
            df = df.dropna()
            
            X = df[["lag1", "lag2", "lag3"]].values
            y = df["target"].values
            
            model = LinearRegression()
            model.fit(X, y)
            
            last_features = np.array([[close[-1], close[-2], close[-3]]])
            pred_val = model.predict(last_features)[0]
            
            trend = "UP" if pred_val > close[-1] else "DOWN"
            return {"ml_pred": round(pred_val, 2), "ml_trend": trend}
        except Exception as e:
            return {"ml_pred": None, "ml_trend": "N/A"}

    def _compute_market_breadth(self) -> dict:
        """Tính Market Breadth: Đếm mã tăng/giảm trên toàn sàn HOSE."""
        all_prices = self.db.get_all_latest_prices()
        if not all_prices:
            return {"advance": 0, "decline": 0, "unchanged": 0, "ratio": 0.5}

        advance = sum(1 for p in all_prices if p.get("close", 0) > p.get("open", 0))
        decline = sum(1 for p in all_prices if p.get("close", 0) < p.get("open", 0))
        unchanged = len(all_prices) - advance - decline
        total = advance + decline if (advance + decline) > 0 else 1
        ratio = round(advance / total, 4)

        breadth = {
            "advance": advance,
            "decline": decline,
            "unchanged": unchanged,
            "ratio": ratio,
            "total_stocks": len(all_prices),
        }

        # Lưu DB
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            self.db.insert_market_breadth(
                date=today, total_advance=advance, total_decline=decline,
                total_unchanged=unchanged, breadth_ratio=ratio,
                vnindex_change=0.0, is_keo_tru=False,
            )
        except Exception:
            pass

        return breadth

    # ─── Manual TA Calculations (Fallback khi không có TA-Lib) ──────────

    @staticmethod
    def _manual_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        deltas = np.diff(close)
        rsi = np.full(len(close), np.nan)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(close) - 1):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    @staticmethod
    def _manual_macd(close: np.ndarray) -> tuple:
        def ema(data, period):
            result = np.full(len(data), np.nan)
            result[period - 1] = np.mean(data[:period])
            mult = 2.0 / (period + 1)
            for i in range(period, len(data)):
                result[i] = (data[i] - result[i-1]) * mult + result[i-1]
            return result

        ema12 = ema(close, 12)
        ema26 = ema(close, 26)
        macd_line = ema12 - ema26
        signal = ema(macd_line[~np.isnan(macd_line)], 9)
        macd_sig = np.full(len(close), np.nan)
        valid_start = np.argmax(~np.isnan(macd_line))
        if len(signal) > 0:
            macd_sig[valid_start:valid_start + len(signal)] = signal
        return macd_line, macd_sig

    @staticmethod
    def _manual_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                    period: int = 14) -> np.ndarray:
        atr = np.full(len(close), np.nan)
        tr = np.maximum(high[1:] - low[1:],
                        np.abs(high[1:] - close[:-1]),
                        np.abs(low[1:] - close[:-1]))
        atr[period] = np.mean(tr[:period])
        for i in range(period + 1, len(close)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i-1]) / period
        return atr

    @staticmethod
    def _manual_sma(close: np.ndarray, period: int = 20) -> np.ndarray:
        sma = np.full(len(close), np.nan)
        for i in range(period - 1, len(close)):
            sma[i] = np.mean(close[i - period + 1:i + 1])
        return sma

    @staticmethod
    def _rsi_signal(rsi: float) -> str:
        if rsi >= 70:
            return "QUÁ MUA"
        elif rsi <= 30:
            return "QUÁ BÁN"
        return "TRUNG TÍNH"

    @staticmethod
    def _macd_signal_type(macd_val, macd_sig) -> str:
        if len(macd_val) < 2:
            return "N/A"
        try:
            if macd_val[-1] > macd_sig[-1] and macd_val[-2] <= macd_sig[-2]:
                return "GOLDEN CROSS"
            elif macd_val[-1] < macd_sig[-1] and macd_val[-2] >= macd_sig[-2]:
                return "DEATH CROSS"
            elif macd_val[-1] > macd_sig[-1]:
                return "BULLISH"
            else:
                return "BEARISH"
        except (IndexError, TypeError):
            return "N/A"

    def get_summary(self) -> str:
        result = self.run()
        parts = [f"Phân tích: {result['symbols_analyzed']} mã"]
        b = result["market_breadth"]
        parts.append(f"Breadth: {b['advance']}↑ / {b['decline']}↓ (ratio={b['ratio']:.2f})")
        # Top signals
        for sym, ind in list(result["indicators"].items())[:5]:
            rsi = ind.get("rsi_14", "N/A")
            sig = ind.get("rsi_signal", "")
            parts.append(f"{sym}: RSI={rsi} ({sig}), MACD={ind.get('macd_signal_type','N/A')}")
        return " | ".join(parts)
