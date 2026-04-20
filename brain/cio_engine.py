"""
VNINDEX AI Analyst - CIO Engine
Bộ não trung tâm sử dụng Gemma (via Ollama) để ra quyết định đầu tư.
"""

import json
import logging
from datetime import datetime

import requests

import config
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

CIO_SYSTEM_PROMPT = """Bạn là CEO (Chief Executive Officer) của một quỹ đầu tư chứng khoán Việt Nam.

DỮ LIỆU ĐẦU VÀO gồm 3 phần:
1. VĨ MÔ: Chỉ số DXY, US10Y, Tỷ giá USD/VND và cảnh báo
2. KỸ THUẬT: RSI, MACD, ATR, Market Breadth và Dự báo Machine Learning cho từng mã
3. TIN TỨC: Điểm sentiment từng mã và thị trường chung

QUY TẮC RA QUYẾT ĐỊNH (BẮT BUỘC TUÂN THỦ):
- Nếu Vĩ mô XẤU + Kỹ thuật TỐT → Chỉ được GIỮ, KHÔNG MUA mới
- Nếu Tin tức XẤU + Kỹ thuật XẤU → BÁN ngay lập tức
- Nếu có cảnh báo "Kéo trụ" → KHÔNG MUA, chỉ GIỮ hoặc BÁN
- Nếu Tỷ trọng bị giảm (do tỷ giá) → Giảm khối lượng MUA 50%
- LUÔN ƯU TIÊN BẢO TOÀN VỐN

OUTPUT FORMAT (JSON):
{
  "market_assessment": "Tóm tắt đánh giá thị trường",
  "decisions": [
    {
      "symbol": "MÃ",
      "recommendation": "MUA|BÁN|GIỮ|THEO DÕI",
      "reasoning": "Lý do",
      "confidence": 0.0-1.0,
      "trailing_stop": số hoặc null
    }
  ],
  "risk_level": "THẤP|TRUNG BÌNH|CAO|RẤT CAO",
  "overall_strategy": "Chiến lược tổng thể"
}"""


class CIOEngine:
    """Bộ não CEO sử dụng Gemma 4 via Ollama API."""

    def __init__(self):
        self.db = DatabaseManager()
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.OLLAMA_MODEL

    def analyze(self, macro_data: dict, tech_data: dict,
                news_data: dict, risk_data: dict) -> dict:
        """Phân tích tổng hợp và đưa ra quyết định."""
        logger.info("🧠 CIO Engine: Starting decision process...")

        # Chuẩn bị prompt
        user_prompt = self._build_prompt(macro_data, tech_data, news_data, risk_data)

        # Gọi Ollama
        try:
            response = self._call_ollama(user_prompt)
            decisions = self._parse_response(response)
        except Exception as e:
            logger.error(f"  Ollama call failed: {e}")
            decisions = self._rule_based_fallback(macro_data, tech_data, news_data, risk_data)

        # Lưu decisions vào DB
        today = datetime.now().strftime("%Y-%m-%d")
        for dec in decisions.get("decisions", []):
            try:
                self.db.insert_cio_decision(
                    date=today,
                    symbol=dec.get("symbol", "MARKET"),
                    recommendation=dec.get("recommendation", "THEO DÕI"),
                    reasoning=dec.get("reasoning", ""),
                    trailing_stop=dec.get("trailing_stop"),
                    confidence=dec.get("confidence"),
                    macro_summary=str(macro_data.get("status", "")),
                    tech_summary=str(tech_data.get("symbols_analyzed", 0)),
                    news_summary=str(news_data.get("market_sentiment", 0)),
                )
            except Exception as e:
                logger.debug(f"  DB save error: {e}")

        logger.info(f"🧠 CIO Engine: Done. {len(decisions.get('decisions', []))} decisions made.")
        return decisions

    def _build_prompt(self, macro: dict, tech: dict, news: dict, risk: dict) -> str:
        sections = []

        # Vĩ mô
        sections.append("=== VĨ MÔ ===")
        sections.append(f"DXY: {macro.get('dxy', 'N/A')}")
        sections.append(f"US10Y: {macro.get('us10y', 'N/A')}%")
        sections.append(f"USD/VND: {macro.get('usd_vnd', 'N/A')}")
        sections.append(f"Biến động tỷ giá: {macro.get('exchange_rate_change_pct', 'N/A')}%")
        sections.append(f"Trạng thái: {macro.get('status', 'N/A')}")
        for alert in macro.get("alerts", []):
            sections.append(f"⚠️ {alert.get('message', '')}")

        # Kỹ thuật
        sections.append("\n=== KỸ THUẬT NỔI BẬT ===")
        breadth = tech.get("market_breadth", {})
        sections.append(f"Market Breadth: {breadth.get('advance',0)}↑/{breadth.get('decline',0)}↓ (ratio={breadth.get('ratio',0):.2f})")
        
        all_indicators = tech.get("indicators", {})
        fav_symbols = [t["symbol"] for t in self.db.get_favorite_tickers()]
        
        highlight_symbols = []
        for sym, ind in all_indicators.items():
            if sym in fav_symbols:
                highlight_symbols.append((sym, ind))
                continue
            macd_sig = ind.get("macd_signal_type", "")
            # Chọn lọc các mã có tín hiệu tốt để phân tích sâu
            if macd_sig in ["GOLDEN CROSS", "BULLISH"]:
                highlight_symbols.append((sym, ind))
                
        # Giới hạn số lượng mã đưa vào LLM để không bị tràn context (tối đa 30)
        highlight_symbols = highlight_symbols[:30]
        
        for sym, ind in highlight_symbols:
            sections.append(
                f"{sym}: Close={ind.get('close','N/A')}, RSI={ind.get('rsi_14','N/A')} "
                f"({ind.get('rsi_signal','N/A')}), MACD={ind.get('macd_signal_type','N/A')}, "
                f"ATR={ind.get('atr_14','N/A')}, ML_Pred={ind.get('ml_pred','N/A')} ({ind.get('ml_trend','N/A')})"
            )

        # Tin tức
        sections.append("\n=== TIN TỨC ===")
        sections.append(f"Sentiment thị trường: {news.get('market_sentiment', 0):+.4f}")
        for sym, score in list(news.get("symbol_sentiments", {}).items())[:10]:
            sections.append(f"{sym}: sentiment={score:+.4f}")

        # Rủi ro
        sections.append("\n=== RỦI RO ===")
        sections.append(f"Kéo trụ: {'CÓ' if risk.get('keo_tru_warning') else 'KHÔNG'}")
        sections.append(f"Tỷ trọng cho phép: {risk.get('position_adjustment', 1.0)*100:.0f}%")
        for alert in risk.get("alerts", []):
            sections.append(f"🚨 {alert.get('message', '')}")

        return "\n".join(sections)

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": CIO_SYSTEM_PROMPT,
            "stream": False,
            "options": config.OLLAMA_PARAMS,
        }

        logger.info(f"  Calling Ollama ({self.model})...")
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    def _parse_response(self, response: str) -> dict:
        """Parse JSON từ response của Gemma."""
        # Tìm JSON block trong response
        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            json_str = response[start:end]
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"  Failed to parse JSON response: {e}")
            return {
                "market_assessment": response[:500],
                "decisions": [],
                "risk_level": "TRUNG BÌNH",
                "overall_strategy": "Cần review thủ công",
            }

    def _rule_based_fallback(self, macro: dict, tech: dict,
                              news: dict, risk: dict) -> dict:
        """Fallback khi Ollama không khả dụng - rule-based."""
        logger.info("  Using rule-based fallback...")
        decisions = []

        macro_bad = macro.get("status") == "WARNING"
        keo_tru = risk.get("keo_tru_warning", False)
        position_adj = risk.get("position_adjustment", 1.0)
        market_sentiment = news.get("market_sentiment", 0)

        for symbol, ind in tech.get("indicators", {}).items():
            rsi = ind.get("rsi_14", 50)
            macd_sig = ind.get("macd_signal_type", "N/A")
            sym_sentiment = news.get("symbol_sentiments", {}).get(symbol, 0)

            tech_good = (rsi and 30 < rsi < 70 and macd_sig in ["BULLISH", "GOLDEN CROSS"])
            tech_bad = (rsi and (rsi >= 70 or rsi <= 30) or macd_sig in ["BEARISH", "DEATH CROSS"])
            news_bad = sym_sentiment < -0.3

            # Áp dụng quy tắc
            if news_bad and tech_bad:
                rec = "BÁN"
                reason = f"Tin tức tiêu cực ({sym_sentiment:+.2f}) + Kỹ thuật xấu ({macd_sig})"
            elif macro_bad and tech_good:
                rec = "GIỮ"
                reason = "Vĩ mô xấu nhưng kỹ thuật tốt - chỉ giữ"
            elif keo_tru:
                rec = "GIỮ"
                reason = "Cảnh báo kéo trụ - không mua mới"
            elif tech_good and not macro_bad and sym_sentiment > 0:
                rec = "MUA"
                reason = f"Kỹ thuật tốt + Sentiment tích cực ({sym_sentiment:+.2f})"
            else:
                rec = "THEO DÕI"
                reason = "Chưa đủ tín hiệu rõ ràng"

            trailing = risk.get("trailing_stops", {}).get(symbol, {}).get("stop_loss")

            decisions.append({
                "symbol": symbol,
                "recommendation": rec,
                "reasoning": reason,
                "confidence": 0.6,
                "trailing_stop": trailing,
            })

        risk_level = "CAO" if (macro_bad or keo_tru) else ("TRUNG BÌNH" if market_sentiment < 0 else "THẤP")

        return {
            "market_assessment": f"Phân tích rule-based. Vĩ mô: {'Xấu' if macro_bad else 'Ổn'}, Sentiment: {market_sentiment:+.4f}",
            "decisions": decisions,
            "risk_level": risk_level,
            "overall_strategy": "Ưu tiên bảo toàn vốn" if risk_level in ["CAO", "RẤT CAO"] else "Chọn lọc cổ phiếu tốt",
        }
