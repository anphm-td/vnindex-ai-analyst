"""
VNINDEX AI Analyst - Database Manager
CRUD operations cho tất cả các bảng.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional

from .models import get_connection

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Quản lý tất cả thao tác CRUD với SQLite."""

    # ─── Tickers ───────────────────────────────────────────────────────────

    @staticmethod
    def upsert_ticker(symbol: str, company_name: str,
                      industry: str = None, exchange: str = "HOSE"):
        """Thêm hoặc cập nhật thông tin cổ phiếu."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO tickers (symbol, company_name, industry, exchange)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(symbol) DO UPDATE SET
                       company_name=excluded.company_name,
                       industry=excluded.industry,
                       exchange=excluded.exchange""",
                (symbol, company_name, industry, exchange)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_all_tickers(exchange: str = None) -> list[dict]:
        """Lấy danh sách tất cả mã cổ phiếu."""
        conn = get_connection()
        try:
            if exchange:
                rows = conn.execute(
                    "SELECT * FROM tickers WHERE exchange = ?", (exchange,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tickers").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_favorite_tickers() -> list[dict]:
        """Lấy danh sách mã chứng khoán yêu thích."""
        conn = get_connection()
        try:
            try:
                rows = conn.execute("SELECT * FROM tickers WHERE is_favorite = 1").fetchall()
                return [dict(row) for row in rows]
            except sqlite3.OperationalError:
                return []
        finally:
            conn.close()

    @staticmethod
    def toggle_favorite(symbol: str, is_favorite: bool):
        """Bật/tắt cờ yêu thích cho mã."""
        conn = get_connection()
        try:
            conn.execute("UPDATE tickers SET is_favorite = ? WHERE symbol = ?", 
                         (1 if is_favorite else 0, symbol))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_ticker(symbol: str) -> Optional[dict]:
        """Lấy thông tin một mã cổ phiếu."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM tickers WHERE symbol = ?", (symbol,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ─── Daily Prices ──────────────────────────────────────────────────────

    @staticmethod
    def insert_daily_price(symbol: str, date: str, open_: float, high: float,
                           low: float, close: float, volume: int):
        """Thêm dữ liệu giá hàng ngày."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO daily_prices
                   (symbol, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (symbol, date, open_, high, low, close, volume)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def insert_daily_prices_batch(records: list[tuple]):
        """Thêm hàng loạt dữ liệu giá.
        Mỗi record: (symbol, date, open, high, low, close, volume).
        """
        conn = get_connection()
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO daily_prices
                   (symbol, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                records
            )
            conn.commit()
            logger.info(f"Inserted {len(records)} daily price records.")
        finally:
            conn.close()

    @staticmethod
    def update_technical_indicators(symbol: str, date: str,
                                    rsi_14: float = None, macd: float = None,
                                    macd_signal: float = None,
                                    atr_14: float = None, ma_20: float = None):
        """Cập nhật chỉ báo kỹ thuật cho một phiên."""
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE daily_prices SET
                       rsi_14 = COALESCE(?, rsi_14),
                       macd = COALESCE(?, macd),
                       macd_signal = COALESCE(?, macd_signal),
                       atr_14 = COALESCE(?, atr_14),
                       ma_20 = COALESCE(?, ma_20)
                   WHERE symbol = ? AND date = ?""",
                (rsi_14, macd, macd_signal, atr_14, ma_20, symbol, date)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_recent_prices(symbol: str, limit: int = 50) -> list[dict]:
        """Lấy N phiên giao dịch gần nhất của mã cổ phiếu."""
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM daily_prices
                   WHERE symbol = ?
                   ORDER BY date DESC
                   LIMIT ?""",
                (symbol, limit)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_latest_price(symbol: str) -> Optional[dict]:
        """Lấy dữ liệu giá mới nhất."""
        conn = get_connection()
        try:
            row = conn.execute(
                """SELECT * FROM daily_prices
                   WHERE symbol = ?
                   ORDER BY date DESC LIMIT 1""",
                (symbol,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_all_latest_prices(date: str = None) -> list[dict]:
        """Lấy giá mới nhất của tất cả mã (cho Market Breadth)."""
        conn = get_connection()
        try:
            if date:
                rows = conn.execute(
                    """SELECT dp.*, t.company_name, t.industry, t.exchange
                       FROM daily_prices dp
                       JOIN tickers t ON dp.symbol = t.symbol
                       WHERE dp.date = ?""",
                    (date,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT dp.*, t.company_name, t.industry, t.exchange
                       FROM daily_prices dp
                       JOIN tickers t ON dp.symbol = t.symbol
                       WHERE dp.date = (SELECT MAX(date) FROM daily_prices)"""
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ─── Market News ───────────────────────────────────────────────────────

    @staticmethod
    def insert_news(symbol: str, publish_date: str, title: str,
                    content_summary: str = None, sentiment_score: float = None,
                    source: str = None):
        """Thêm tin tức mới."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO market_news
                   (symbol, publish_date, title, content_summary,
                    sentiment_score, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (symbol, publish_date, title, content_summary,
                 sentiment_score, source)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_recent_news(symbol: str = None, limit: int = 20) -> list[dict]:
        """Lấy tin tức gần nhất, có thể lọc theo mã."""
        conn = get_connection()
        try:
            if symbol:
                rows = conn.execute(
                    """SELECT * FROM market_news
                       WHERE symbol = ?
                       ORDER BY publish_date DESC LIMIT ?""",
                    (symbol, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM market_news
                       ORDER BY publish_date DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_sentiment_summary(date: str = None) -> list[dict]:
        """Lấy điểm sentiment trung bình theo mã cổ phiếu."""
        conn = get_connection()
        try:
            query = """
                SELECT symbol,
                       AVG(sentiment_score) as avg_sentiment,
                       COUNT(*) as news_count
                FROM market_news
                WHERE sentiment_score IS NOT NULL
            """
            params = []
            if date:
                query += " AND publish_date >= ?"
                params.append(date)
            query += " GROUP BY symbol ORDER BY avg_sentiment DESC"

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ─── Macro Data ────────────────────────────────────────────────────────

    @staticmethod
    def insert_macro_data(date: str, indicator: str, value: float):
        """Thêm dữ liệu vĩ mô."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO macro_data (date, indicator, value)
                   VALUES (?, ?, ?)""",
                (date, indicator, value)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_macro_data(indicator: str, days: int = 30) -> list[dict]:
        """Lấy dữ liệu vĩ mô theo indicator."""
        conn = get_connection()
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            rows = conn.execute(
                """SELECT * FROM macro_data
                   WHERE indicator = ? AND date >= ?
                   ORDER BY date DESC""",
                (indicator, cutoff)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ─── CIO Decisions ─────────────────────────────────────────────────────

    @staticmethod
    def insert_cio_decision(date: str, symbol: str, recommendation: str,
                            reasoning: str, trailing_stop: float = None,
                            confidence: float = None, macro_summary: str = None,
                            tech_summary: str = None, news_summary: str = None):
        """Lưu quyết định của CIO."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO cio_decisions
                   (date, symbol, recommendation, reasoning, trailing_stop,
                    confidence, macro_summary, tech_summary, news_summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date, symbol, recommendation, reasoning, trailing_stop,
                 confidence, macro_summary, tech_summary, news_summary)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_latest_decisions(date: str = None) -> list[dict]:
        """Lấy quyết định CIO mới nhất."""
        conn = get_connection()
        try:
            if date:
                rows = conn.execute(
                    """SELECT * FROM cio_decisions
                       WHERE date = ?
                       ORDER BY created_at DESC""",
                    (date,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM cio_decisions
                       WHERE date = (SELECT MAX(date) FROM cio_decisions)
                       ORDER BY created_at DESC"""
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ─── Market Breadth ────────────────────────────────────────────────────

    @staticmethod
    def insert_market_breadth(date: str, total_advance: int,
                              total_decline: int, total_unchanged: int,
                              breadth_ratio: float, vnindex_change: float,
                              is_keo_tru: bool = False):
        """Lưu dữ liệu Market Breadth."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO market_breadth
                   (date, total_advance, total_decline, total_unchanged,
                    breadth_ratio, vnindex_change, is_keo_tru)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (date, total_advance, total_decline, total_unchanged,
                 breadth_ratio, vnindex_change, int(is_keo_tru))
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_market_breadth(days: int = 30) -> list[dict]:
        """Lấy dữ liệu Market Breadth gần nhất."""
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM market_breadth
                   ORDER BY date DESC LIMIT ?""",
                (days,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
