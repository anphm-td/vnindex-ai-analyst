"""
VNINDEX AI Analyst - Risk Manager
Kiểm soát rủi ro: Kéo trụ, Trailing Stop, Tỷ trọng.
"""

import logging
from datetime import datetime

import config
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Agent kiểm soát rủi ro:
    - Cảnh báo "Xanh vỏ đỏ lòng" (Kéo trụ)
    - Tính Trailing Stop = Price_Max - (2.5 * ATR)
    - Giảm tỷ trọng khi tỷ giá căng thẳng
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.alerts = []

    def run(self, macro_result: dict = None, tech_result: dict = None) -> dict:
        logger.info("🛡️ Risk Manager: Starting analysis...")
        self.alerts = []

        result = {
            "keo_tru_warning": False,
            "trailing_stops": {},
            "position_adjustment": 1.0,  # 1.0 = 100%, 0.5 = giảm 50%
            "alerts": [],
            "timestamp": datetime.now().isoformat(),
        }

        # 1. Kiểm tra Kéo trụ
        if tech_result:
            keo_tru = self._check_keo_tru(tech_result)
            result["keo_tru_warning"] = keo_tru

        # 2. Tính Trailing Stop cho từng mã
        if tech_result and "indicators" in tech_result:
            for symbol, ind in tech_result["indicators"].items():
                stop = self._calc_trailing_stop(symbol, ind)
                if stop:
                    result["trailing_stops"][symbol] = stop

        # 3. Kiểm tra áp lực tỷ giá → Giảm tỷ trọng
        if macro_result:
            adjustment = self._check_position_adjustment(macro_result)
            result["position_adjustment"] = adjustment

        result["alerts"] = self.alerts
        logger.info(f"🛡️ Risk Manager: Done. {len(self.alerts)} alerts.")
        return result

    def _check_keo_tru(self, tech_result: dict) -> bool:
        """
        Cảnh báo Kéo trụ:
        VNINDEX tăng > 1% nhưng Market Breadth < 0.5 → "Xanh vỏ đỏ lòng"
        """
        breadth = tech_result.get("market_breadth", {})
        ratio = breadth.get("ratio", 0.5)

        # Lấy VNINDEX change từ breadth hoặc tính từ dữ liệu
        vnindex_data = self.db.get_recent_prices("VNINDEX", limit=2)
        vnindex_change = 0.0
        if len(vnindex_data) >= 2:
            prev_close = vnindex_data[1].get("close", 0)
            curr_close = vnindex_data[0].get("close", 0)
            if prev_close > 0:
                vnindex_change = (curr_close - prev_close) / prev_close

        is_keo_tru = (
            vnindex_change > config.VNINDEX_SURGE_THRESHOLD
            and ratio < config.MARKET_BREADTH_THRESHOLD
        )

        if is_keo_tru:
            alert = {
                "type": "KEO_TRU",
                "message": (
                    f"🔴 XANH VỎ ĐỎ LÒNG: VNINDEX tăng {vnindex_change*100:.2f}% "
                    f"nhưng chỉ {ratio*100:.1f}% mã tăng"
                ),
                "severity": "HIGH",
                "vnindex_change": vnindex_change,
                "breadth_ratio": ratio,
            }
            self.alerts.append(alert)
            logger.warning(f"  {alert['message']}")

            # Cập nhật DB
            today = datetime.now().strftime("%Y-%m-%d")
            try:
                self.db.insert_market_breadth(
                    date=today,
                    total_advance=breadth.get("advance", 0),
                    total_decline=breadth.get("decline", 0),
                    total_unchanged=breadth.get("unchanged", 0),
                    breadth_ratio=ratio,
                    vnindex_change=vnindex_change,
                    is_keo_tru=True,
                )
            except Exception:
                pass

        return is_keo_tru

    def _calc_trailing_stop(self, symbol: str, indicators: dict) -> dict | None:
        """Trailing Stop = Price_Max - (2.5 * ATR)."""
        atr = indicators.get("atr_14")
        close = indicators.get("close")

        if not atr or not close:
            return None

        # Tìm Price Max trong 20 phiên gần nhất
        prices = self.db.get_recent_prices(symbol, limit=20)
        if not prices:
            return None

        price_max = max(p["high"] for p in prices)
        stop_loss = round(price_max - (config.TRAILING_STOP_ATR_MULTIPLIER * atr), 2)
        distance_pct = round(((close - stop_loss) / close) * 100, 2) if close > 0 else 0

        result = {
            "symbol": symbol,
            "current_price": close,
            "price_max_20": price_max,
            "atr_14": atr,
            "stop_loss": stop_loss,
            "distance_pct": distance_pct,
        }

        # Cảnh báo nếu giá gần stop
        if distance_pct < 2.0 and distance_pct > 0:
            alert = {
                "type": "NEAR_STOP",
                "message": f"⚠️ {symbol}: Giá ({close:,.0f}) chỉ cách stop ({stop_loss:,.0f}) {distance_pct:.1f}%",
                "severity": "MEDIUM",
                "symbol": symbol,
            }
            self.alerts.append(alert)

        if close < stop_loss:
            alert = {
                "type": "STOP_TRIGGERED",
                "message": f"🔴 {symbol}: ĐÃ CHẠM STOP LOSS! Giá {close:,.0f} < Stop {stop_loss:,.0f}",
                "severity": "CRITICAL",
                "symbol": symbol,
            }
            self.alerts.append(alert)

        return result

    def _check_position_adjustment(self, macro_result: dict) -> float:
        """Giảm 50% tỷ trọng nếu tỷ giá căng thẳng."""
        alerts = macro_result.get("alerts", [])
        for alert in alerts:
            if alert.get("type") == "EXCHANGE_RATE_PRESSURE":
                self.alerts.append({
                    "type": "POSITION_REDUCE",
                    "message": "📉 Giảm 50% khối lượng MUA do áp lực tỷ giá",
                    "severity": "HIGH",
                })
                logger.warning("  Position reduced to 50% due to exchange rate pressure")
                return 0.5
        return 1.0

    def get_summary(self) -> str:
        result = self.run()
        parts = []
        if result["keo_tru_warning"]:
            parts.append("🔴 CẢNH BÁO KÉO TRỤ")
        if result["position_adjustment"] < 1.0:
            parts.append(f"Tỷ trọng: {result['position_adjustment']*100:.0f}%")
        stops = result["trailing_stops"]
        for sym, s in list(stops.items())[:5]:
            parts.append(f"{sym}: Stop={s['stop_loss']:,.0f} (cách {s['distance_pct']:.1f}%)")
        if not parts:
            parts.append("✅ Không có cảnh báo rủi ro")
        return " | ".join(parts)
