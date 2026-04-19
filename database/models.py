"""
VNINDEX AI Analyst - Database Models
Định nghĩa schema SQLite cho toàn bộ hệ thống.
"""

import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

# ─── SQL Tạo bảng ──────────────────────────────────────────────────────────────

CREATE_TICKERS = """
CREATE TABLE IF NOT EXISTS tickers (
    symbol      TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry    TEXT,
    exchange    TEXT CHECK(exchange IN ('HOSE', 'HNX', 'UPCOM'))
);
"""

CREATE_DAILY_PRICES = """
CREATE TABLE IF NOT EXISTS daily_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    rsi_14      REAL,
    macd        REAL,
    macd_signal REAL,
    atr_14      REAL,
    ma_20       REAL,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol),
    UNIQUE(symbol, date)
);
"""

CREATE_DAILY_PRICES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol_date
ON daily_prices(symbol, date DESC);
"""

CREATE_MARKET_NEWS = """
CREATE TABLE IF NOT EXISTS market_news (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT,
    publish_date    TEXT NOT NULL,
    title           TEXT NOT NULL,
    content_summary TEXT,
    sentiment_score REAL CHECK(sentiment_score >= -1.0 AND sentiment_score <= 1.0),
    source          TEXT,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);
"""

CREATE_MARKET_NEWS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_market_news_symbol_date
ON market_news(symbol, publish_date DESC);
"""

CREATE_MACRO_DATA = """
CREATE TABLE IF NOT EXISTS macro_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    indicator   TEXT NOT NULL,
    value       REAL,
    UNIQUE(date, indicator)
);
"""

CREATE_MACRO_DATA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_macro_data_date
ON macro_data(date DESC);
"""

CREATE_CIO_DECISIONS = """
CREATE TABLE IF NOT EXISTS cio_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    symbol          TEXT,
    recommendation  TEXT CHECK(recommendation IN ('MUA', 'BÁN', 'GIỮ', 'THEO DÕI')),
    reasoning       TEXT,
    trailing_stop   REAL,
    confidence      REAL,
    macro_summary   TEXT,
    tech_summary    TEXT,
    news_summary    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""

CREATE_CIO_DECISIONS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_cio_decisions_date
ON cio_decisions(date DESC);
"""

CREATE_MARKET_BREADTH = """
CREATE TABLE IF NOT EXISTS market_breadth (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,
    total_advance   INTEGER,
    total_decline   INTEGER,
    total_unchanged INTEGER,
    breadth_ratio   REAL,
    vnindex_change  REAL,
    is_keo_tru      INTEGER DEFAULT 0
);
"""

ALL_TABLES = [
    CREATE_TICKERS,
    CREATE_DAILY_PRICES,
    CREATE_DAILY_PRICES_INDEX,
    CREATE_MARKET_NEWS,
    CREATE_MARKET_NEWS_INDEX,
    CREATE_MACRO_DATA,
    CREATE_MACRO_DATA_INDEX,
    CREATE_CIO_DECISIONS,
    CREATE_CIO_DECISIONS_INDEX,
    CREATE_MARKET_BREADTH,
]


def init_db():
    """Khởi tạo tất cả bảng trong database."""
    logger.info(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    for sql in ALL_TABLES:
        cursor.execute(sql)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")


def get_connection():
    """Trả về connection tới SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Tối ưu cho concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"✅ Database created at: {DB_PATH}")
