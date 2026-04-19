"""
Script kéo dữ liệu giá chứng khoán (OHLC) từ thư viện vnstock.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging
from datetime import datetime, timedelta
import pandas as pd
from vnstock import stock_historical_data

from database.models import init_db
from database.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DataFetcher")

def run_fetcher(days: int = 150):
    db = DatabaseManager()
    tickers = db.get_all_tickers()
    
    if not tickers:
        logger.error("Không có mã cổ phiếu nào trong DB. Vui lòng chạy `python seed_data.py` trước.")
        return

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    logger.info(f"Kéo dữ liệu từ {start_date} đến {end_date} cho {len(tickers)} mã...")
    
    all_records = []
    
    for t in tickers:
        symbol = t["symbol"]
        try:
            # Tham số vnstock: symbol, start_date, end_date, resolution, type
            if symbol == "VNINDEX":
                df = stock_historical_data(symbol, start_date, end_date, "1D", "index")
            else:
                df = stock_historical_data(symbol, start_date, end_date, "1D", "stock")
                
            if df is not None and not df.empty:
                count = 0
                for _, row in df.iterrows():
                    # Xử lý format cột thời gian
                    time_val = row.get("time", row.get("Date", None))
                    date_str = str(time_val).split(" ")[0] if time_val else None
                    if not date_str:
                        continue
                    
                    # vnstock có thể trả về 'open' hoặc 'Open'
                    open_p = float(row.get("open", row.get("Open", 0)))
                    high_p = float(row.get("high", row.get("High", 0)))
                    low_p = float(row.get("low", row.get("Low", 0)))
                    close_p = float(row.get("close", row.get("Close", 0)))
                    vol = int(row.get("volume", row.get("Volume", 0)))
                    
                    all_records.append((symbol, date_str, open_p, high_p, low_p, close_p, vol))
                    count += 1
                logger.info(f"✅ {symbol}: {count} phiên giao dịch")
            else:
                logger.warning(f"❌ {symbol}: Không lấy được dữ liệu")
                
        except Exception as e:
            logger.error(f"❌ {symbol} - Lỗi: {e}")

    if all_records:
        db.insert_daily_prices_batch(all_records)
        logger.info(f"🎉 Đã lưu {len(all_records)} bản ghi vào database.")
    else:
        logger.warning("Không có dữ liệu nào được lưu.")

if __name__ == "__main__":
    init_db()
    run_fetcher(150)  # Lấy 150 ngày để đủ tính MA200 hoặc các chỉ báo dài hạn
