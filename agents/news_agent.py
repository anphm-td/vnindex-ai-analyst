"""
VNINDEX AI Analyst - News Agent
Crawl tin tức chứng khoán Việt Nam + Phân tích sentiment.
"""

import re
import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

_sentiment_pipeline = None


def _get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is not None:
        return _sentiment_pipeline
    try:
        from transformers import pipeline
        logger.info("Loading PhoBERT sentiment model...")
        _sentiment_pipeline = pipeline(
            "text-classification",
            model=config.PHOBERT_MODEL,
            tokenizer=config.PHOBERT_MODEL,
            device=-1,
        )
        logger.info("PhoBERT loaded successfully.")
    except Exception as e:
        logger.warning(f"PhoBERT not available: {e}. Using keyword-based sentiment.")
        _sentiment_pipeline = "keyword_fallback"
    return _sentiment_pipeline


class NewsAgent:
    TICKER_PATTERN = re.compile(r'\b([A-Z]{3,5})\b')
    EXCLUDE_WORDS = {"THE", "CUA", "CHO", "VOI", "VAN", "SAU", "MOT",
                     "HAI", "BAO", "TAI", "NAM", "NGA", "BAN", "MUA", "TIN"}

    def __init__(self):
        self.db = DatabaseManager()
        self._known_tickers = set()
        self._load_known_tickers()

    def _load_known_tickers(self):
        tickers = self.db.get_all_tickers()
        self._known_tickers = {t["symbol"] for t in tickers}

    def run(self) -> dict:
        logger.info("📰 News Agent: Starting analysis...")
        all_articles = []
        sentiment_map = {}

        for source_name, source_config in config.NEWS_SOURCES.items():
            try:
                articles = self._crawl_rss(source_config["rss_url"], source_name)
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"  {source_name}: Crawl failed - {e}")

        for article in all_articles:
            symbols = self._extract_tickers(article["title"])
            score = self._analyze_sentiment(article["title"])
            target_symbol = symbols[0] if symbols else None

            for symbol in (symbols or [None]):
                if symbol:
                    sentiment_map.setdefault(symbol, []).append(score)
                try:
                    self.db.insert_news(
                        symbol=symbol,
                        publish_date=article.get("date", datetime.now().strftime("%Y-%m-%d")),
                        title=article["title"],
                        content_summary=article.get("summary", ""),
                        sentiment_score=score,
                        source=article.get("source", "unknown"),
                    )
                except Exception:
                    pass

        avg_sentiments = {s: round(sum(sc)/len(sc), 4) for s, sc in sentiment_map.items()}
        all_scores = [s for sc in sentiment_map.values() for s in sc]
        market_sentiment = round(sum(all_scores)/len(all_scores), 4) if all_scores else 0.0

        result = {
            "total_articles": len(all_articles),
            "symbol_sentiments": avg_sentiments,
            "market_sentiment": market_sentiment,
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(f"📰 News Agent: Done. {len(all_articles)} articles, sentiment={market_sentiment:+.4f}")
        return result

    def _crawl_rss(self, rss_url: str, source: str, limit: int = 20) -> list[dict]:
        try:
            resp = requests.get(rss_url, timeout=15,
                                headers={"User-Agent": "Mozilla/5.0 (VNINDEX AI Analyst)"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "xml")
            articles = []
            for item in soup.find_all("item", limit=limit):
                title = item.find("title")
                if title:
                    desc = item.find("description")
                    pub = item.find("pubDate")
                    articles.append({
                        "title": title.get_text(strip=True),
                        "summary": desc.get_text(strip=True) if desc else "",
                        "date": self._parse_date(pub.get_text(strip=True)) if pub else datetime.now().strftime("%Y-%m-%d"),
                        "source": source,
                    })
            return articles
        except Exception as e:
            logger.error(f"RSS error ({source}): {e}")
            return self._mock_articles(source)

    def _parse_date(self, s: str) -> str:
        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                     "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"]:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return datetime.now().strftime("%Y-%m-%d")

    def _extract_tickers(self, text: str) -> list[str]:
        found = self.TICKER_PATTERN.findall(text)
        return [f for f in found
                if f in self._known_tickers or (len(f) == 3 and f not in self.EXCLUDE_WORDS)]

    def _llama_sentiment(self, text: str) -> float:
        """Sử dụng Llama 3 (Ollama) để phân tích Sentiment."""
        try:
            import json
            prompt = (
                "Phân tích tiêu đề tin tức tài chính sau và trả về DUY NHẤT một con số từ -1.0 đến 1.0 "
                "thể hiện mức độ tích cực/tiêu cực (-1.0: rất xấu, 0: bình thường, 1.0: rất tốt). "
                f"Tin tức: '{text}'\nChỉ trả về số, không giải thích."
            )
            payload = {
                "model": config.OLLAMA_NEWS_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0}
            }
            resp = requests.post(f"{config.OLLAMA_BASE_URL}/api/generate", json=payload, timeout=15)
            if resp.status_code == 200:
                res_text = resp.json().get("response", "0").strip()
                match = re.search(r'-?\d+(\.\d+)?', res_text)
                if match:
                    return max(-1.0, min(1.0, float(match.group())))
            return self._keyword_sentiment(text)
        except Exception as e:
            logger.debug(f"Llama sentiment failed: {e}")
            return self._keyword_sentiment(text)

    def _analyze_sentiment(self, text: str) -> float:
        # Sử dụng Llama 3 thay cho PhoBERT
        return self._llama_sentiment(text)

    def _keyword_sentiment(self, text: str) -> float:
        t = text.lower()
        pos = sum(1 for kw in config.POSITIVE_KEYWORDS if kw in t)
        neg = sum(1 for kw in config.NEGATIVE_KEYWORDS if kw in t)
        total = pos + neg
        return round(max(-1.0, min(1.0, (pos - neg) / total)), 4) if total else 0.0

    def _mock_articles(self, source: str) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            {"title": "VNM báo lợi nhuận quý I tăng trưởng 15% vượt kế hoạch",
             "summary": "Vinamilk ghi nhận kết quả kinh doanh tích cực",
             "date": today, "source": source},
            {"title": "HPG mở rộng nhà máy Dung Quất giai đoạn 3",
             "summary": "Hòa Phát đầu tư thêm", "date": today, "source": source},
            {"title": "SSI bị thanh tra thuế, cổ phiếu giảm mạnh",
             "summary": "Cơ quan thuế vào cuộc", "date": today, "source": source},
            {"title": "FPT ký thương vụ AI trị giá 200 triệu USD tại Nhật Bản",
             "summary": "FPT mở rộng mảng AI", "date": today, "source": source},
        ]

    def get_summary(self) -> str:
        result = self.run()
        parts = [f"Tổng: {result['total_articles']} tin",
                 f"Sentiment TT: {result['market_sentiment']:+.4f}"]
        s = result["symbol_sentiments"]
        if s:
            sorted_s = sorted(s.items(), key=lambda x: x[1], reverse=True)
            top_pos = [(k, v) for k, v in sorted_s if v > 0][:3]
            top_neg = [(k, v) for k, v in sorted_s if v < 0][:3]
            if top_pos:
                parts.append("Tích cực: " + ", ".join(f"{k}({v:+.2f})" for k, v in top_pos))
            if top_neg:
                parts.append("Tiêu cực: " + ", ".join(f"{k}({v:+.2f})" for k, v in top_neg))
        return " | ".join(parts)
