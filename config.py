"""
VNINDEX AI Analyst - Configuration Module
Tập trung tất cả cấu hình hệ thống tại một nơi.
"""

import os
from pathlib import Path

# ─── Đường dẫn ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "vnindex.db"
REPORTS_DIR = DATA_DIR / "reports"

# Tạo thư mục nếu chưa tồn tại
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Database ──────────────────────────────────────────────────────────────────
SQLITE_URI = f"sqlite:///{DB_PATH}"

# ─── FRED API (Dữ liệu vĩ mô Mỹ) ────────────────────────────────────────────
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
# Series IDs
FRED_DXY_SERIES = "DTWEXBGS"      # Trade Weighted U.S. Dollar Index
FRED_US10Y_SERIES = "DGS10"       # 10-Year Treasury Constant Maturity Rate

# ─── Vietcombank Tỷ giá ───────────────────────────────────────────────────────
VCB_EXCHANGE_RATE_URL = "https://portal.vietcombank.com.vn/Usercontrols/TV498/pXML.aspx"

# ─── News Sources ──────────────────────────────────────────────────────────────
NEWS_SOURCES = {
    "cafef": {
        "base_url": "https://cafef.vn",
        "rss_url": "https://cafef.vn/rss/thi-truong-chung-khoan.rss",
    },
    "vietstock": {
        "base_url": "https://vietstock.vn",
        "rss_url": "https://vietstock.vn/rss/chung-khoan.rss",
    },
}
NEWS_FETCH_LIMIT = 20  # Số tin tối đa mỗi lần crawl

# ─── Ollama / Gemma 4 ─────────────────────────────────────────────────────────
# Ollama Settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")  # Model chính cho CEO
OLLAMA_NEWS_MODEL = os.getenv("OLLAMA_NEWS_MODEL", "llama3")  # Model đọc báo
OLLAMA_REPORT_MODEL = os.getenv("OLLAMA_REPORT_MODEL", "qwen2.5")  # Model viết báo cáo
OLLAMA_FUNDAMENTAL_MODEL = os.getenv("OLLAMA_FUNDAMENTAL_MODEL", "deepseek-r1:8b")  # Phân tích cơ bản

# Parameters cho LLM
OLLAMA_PARAMS = {
    "temperature": 0.2,
    "top_p": 0.9,
    "num_predict": 2048,
}

# ─── Technical Analysis ───────────────────────────────────────────────────────
TA_RSI_PERIOD = 14
TA_MACD_FAST = 12
TA_MACD_SLOW = 26
TA_MACD_SIGNAL = 9
TA_ATR_PERIOD = 14
TA_MA_PERIOD = 20
TA_LOOKBACK_SESSIONS = 50  # Số phiên lấy dữ liệu

# ─── Risk Management ──────────────────────────────────────────────────────────
TRAILING_STOP_ATR_MULTIPLIER = 2.5
MARKET_BREADTH_THRESHOLD = 0.5
VNINDEX_SURGE_THRESHOLD = 0.01  # 1%
EXCHANGE_RATE_ALERT_THRESHOLD = 0.005  # 0.5%
EXCHANGE_RATE_MA_WINDOW = 5  # Trung bình 5 ngày

# ─── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULE_MACRO = "08:00"
SCHEDULE_FUNDAMENTAL = "08:05"
SCHEDULE_NEWS = "08:10"
SCHEDULE_TECHNICAL = "08:20"
SCHEDULE_CIO = "08:30"
SCHEDULE_REPORT = "08:45"

# ─── Streamlit ─────────────────────────────────────────────────────────────────
STREAMLIT_PORT = 8501
STREAMLIT_TITLE = "VNINDEX AI Analyst"

# ─── PhoBERT / NLP ─────────────────────────────────────────────────────────────
PHOBERT_MODEL = "vinai/phobert-base-v2"
PHONLP_MODEL = "vinai/PhoNLP"

# ─── Sentiment Keywords (Fallback nếu model chưa sẵn sàng) ────────────────────
POSITIVE_KEYWORDS = [
    "vượt kế hoạch", "tăng trưởng", "lợi nhuận tăng", "đột phá",
    "tích cực", "khả quan", "bứt phá", "kỷ lục", "tăng mạnh",
    "chiến thắng", "phục hồi", "cơ hội", "triển vọng",
]
NEGATIVE_KEYWORDS = [
    "thanh tra", "vi phạm", "thua lỗ", "giảm mạnh", "bán tháo",
    "cảnh báo", "rủi ro", "khủng hoảng", "phá sản", "nợ xấu",
    "điều tra", "xử phạt", "tạm dừng", "đình chỉ",
]
