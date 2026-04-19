"""
VNINDEX AI Analyst - Macro Agent
Chuyên gia phân tích vĩ mô: DXY, US10Y, Tỷ giá USD/VND.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

import requests

import config
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class MacroAgent:
    """
    Agent phân tích dữ liệu vĩ mô:
    - Chỉ số DXY (USD Index) từ FRED
    - Lãi suất US 10Y Treasury từ FRED
    - Tỷ giá USD/VND từ Vietcombank XML
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.alerts = []

    def run(self) -> dict:
        """Chạy toàn bộ pipeline phân tích vĩ mô."""
        logger.info("🌍 Macro Agent: Starting analysis...")
        self.alerts = []
        result = {
            "dxy": None,
            "us10y": None,
            "usd_vnd": None,
            "exchange_rate_change_pct": None,
            "alerts": [],
            "status": "OK",
            "timestamp": datetime.now().isoformat(),
        }

        # 1. Lấy DXY
        try:
            dxy = self._fetch_fred_data(config.FRED_DXY_SERIES)
            if dxy is not None:
                result["dxy"] = dxy
                self.db.insert_macro_data(
                    datetime.now().strftime("%Y-%m-%d"), "DXY", dxy
                )
                logger.info(f"  DXY: {dxy}")
        except Exception as e:
            logger.error(f"  Failed to fetch DXY: {e}")

        # 2. Lấy US10Y
        try:
            us10y = self._fetch_fred_data(config.FRED_US10Y_SERIES)
            if us10y is not None:
                result["us10y"] = us10y
                self.db.insert_macro_data(
                    datetime.now().strftime("%Y-%m-%d"), "US10Y", us10y
                )
                logger.info(f"  US10Y: {us10y}%")
        except Exception as e:
            logger.error(f"  Failed to fetch US10Y: {e}")

        # 3. Lấy tỷ giá VCB
        try:
            usd_vnd = self._fetch_vcb_exchange_rate()
            if usd_vnd is not None:
                result["usd_vnd"] = usd_vnd
                self.db.insert_macro_data(
                    datetime.now().strftime("%Y-%m-%d"), "USD_VND", usd_vnd
                )
                logger.info(f"  USD/VND (Bán ra): {usd_vnd:,.0f}")

                # 4. Kiểm tra biến động tỷ giá
                change_pct = self._check_exchange_rate_pressure(usd_vnd)
                result["exchange_rate_change_pct"] = change_pct

                if change_pct is not None and abs(change_pct) > config.EXCHANGE_RATE_ALERT_THRESHOLD * 100:
                    alert = {
                        "type": "EXCHANGE_RATE_PRESSURE",
                        "message": f"⚠️ Áp lực tỷ giá: USD/VND biến động {change_pct:+.2f}% so với TB 5 ngày",
                        "severity": "HIGH" if abs(change_pct) > 1.0 else "MEDIUM",
                        "value": usd_vnd,
                        "change_pct": change_pct,
                    }
                    self.alerts.append(alert)
                    logger.warning(f"  {alert['message']}")
        except Exception as e:
            logger.error(f"  Failed to fetch VCB exchange rate: {e}")

        result["alerts"] = self.alerts
        if self.alerts:
            result["status"] = "WARNING"

        logger.info(f"🌍 Macro Agent: Completed. Status={result['status']}")
        return result

    def _fetch_fred_data(self, series_id: str) -> Optional[float]:
        """Lấy giá trị mới nhất từ FRED API."""
        if not config.FRED_API_KEY:
            logger.warning("  FRED_API_KEY not set. Using mock data.")
            return self._get_mock_fred_data(series_id)

        params = {
            "series_id": series_id,
            "api_key": config.FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }

        try:
            resp = requests.get(config.FRED_BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            observations = data.get("observations", [])
            if observations:
                value = observations[0].get("value")
                if value and value != ".":
                    return float(value)
        except requests.RequestException as e:
            logger.error(f"  FRED API error for {series_id}: {e}")

        return None

    def _get_mock_fred_data(self, series_id: str) -> float:
        """Dữ liệu mô phỏng khi chưa có API key."""
        mock = {
            config.FRED_DXY_SERIES: 104.25,
            config.FRED_US10Y_SERIES: 4.35,
        }
        return mock.get(series_id, 0.0)

    def _fetch_vcb_exchange_rate(self) -> Optional[float]:
        """Parse XML tỷ giá USD/VND từ Vietcombank (giá Bán ra)."""
        try:
            resp = requests.get(config.VCB_EXCHANGE_RATE_URL, timeout=10)
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            # Tìm thẻ Exrate có CurrencyCode="USD"
            for exrate in root.iter("Exrate"):
                if exrate.get("CurrencyCode") == "USD":
                    sell = exrate.get("Sell", "0")
                    # VCB format: "25,475" -> chuyển sang float
                    sell_value = float(sell.replace(",", ""))
                    return sell_value

            logger.warning("  USD not found in VCB XML response.")
        except requests.RequestException as e:
            logger.error(f"  VCB exchange rate fetch error: {e}")
        except ET.ParseError as e:
            logger.error(f"  VCB XML parse error: {e}")
            # Fallback: mock data
            logger.info("  Using mock USD/VND rate.")
            return 25_475.0

        return None

    def _check_exchange_rate_pressure(self, current_rate: float) -> Optional[float]:
        """
        So sánh tỷ giá hiện tại với trung bình 5 ngày.
        Trả về % biến động. Nếu > 0.5% -> cảnh báo áp lực.
        """
        history = self.db.get_macro_data("USD_VND", days=10)

        if len(history) < config.EXCHANGE_RATE_MA_WINDOW:
            logger.info("  Not enough historical data for exchange rate pressure check.")
            return None

        # Lấy 5 giá trị gần nhất (không tính hôm nay)
        recent_values = [r["value"] for r in history[1:config.EXCHANGE_RATE_MA_WINDOW + 1]]
        if not recent_values:
            return None

        ma_5 = sum(recent_values) / len(recent_values)
        change_pct = ((current_rate - ma_5) / ma_5) * 100

        return round(change_pct, 4)

    def get_summary(self) -> str:
        """Tóm tắt cho CIO Engine."""
        result = self.run()
        parts = []

        if result["dxy"]:
            parts.append(f"DXY: {result['dxy']}")
        if result["us10y"]:
            parts.append(f"US10Y: {result['us10y']}%")
        if result["usd_vnd"]:
            parts.append(f"USD/VND: {result['usd_vnd']:,.0f}")
        if result["exchange_rate_change_pct"]:
            parts.append(f"Tỷ giá biến động: {result['exchange_rate_change_pct']:+.2f}% vs TB5")

        status = "⚠️ CẢNH BÁO" if result["status"] == "WARNING" else "✅ Bình thường"
        parts.append(f"Trạng thái: {status}")

        for alert in result["alerts"]:
            parts.append(f"🚨 {alert['message']}")

        return " | ".join(parts)
