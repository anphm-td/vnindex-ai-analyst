import logging
from pathlib import Path
import sys

# Thêm đường dẫn để import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.models import init_db, get_connection
from database.db_manager import DatabaseManager

try:
    from vnstock import listing_companies
except ImportError:
    print("Vui lòng cài đặt vnstock bằng lệnh: pip install vnstock")
    sys.exit(1)

# Danh sách 30 mã trong rổ VN30 (tính đến thời điểm hiện tại)
VN30_TICKERS = {
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", 
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB", 
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
}

def setup_database_schema():
    """Đảm bảo bảng có cột is_vn30"""
    init_db()
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE tickers ADD COLUMN is_vn30 INTEGER DEFAULT 0")
        conn.commit()
    except Exception as e:
        # Bỏ qua nếu cột đã tồn tại
        pass
    finally:
        conn.close()

def seed_tickers():
    """Lấy danh sách tất cả cổ phiếu trên 3 sàn từ vnstock và lưu vào database."""
    setup_database_schema()
    db = DatabaseManager()
    
    print("Đang tải danh sách công ty từ vnstock...")
    df = listing_companies()
    
    # Lọc ra các mã chứng khoán (bỏ qua chứng quyền, ETF...)
    # Trong vnstock, 'ticker' là mã, 'comGroupCode' là sàn, 'organName' là tên, 'sector' là ngành
    # Lưu ý: Các phiên bản vnstock có thể có tên cột khác nhau
    
    count = 0
    for _, row in df.iterrows():
        try:
            # Lấy thông tin cơ bản
            symbol = str(row.get("ticker", "")).strip()
            if len(symbol) > 5 or not symbol.isalnum():
                continue # Bỏ qua chứng quyền hoặc mã lỗi
                
            name = str(row.get("organName", "")).strip()
            if not name:
                name = str(row.get("organShortName", ""))
                
            industry = str(row.get("sector", "")).strip()
            exchange = str(row.get("comGroupCode", "")).strip()
            
            # Chuẩn hóa tên sàn
            if exchange == "VNINDEX": exchange = "HOSE"
            if exchange == "HNXIndex": exchange = "HNX"
            if exchange == "UpcomIndex": exchange = "UPCOM"
            
            if exchange not in ["HOSE", "HNX", "UPCOM"]:
                continue
                
            db.upsert_ticker(symbol, name, industry, exchange)
            
            # Cập nhật cờ VN30
            is_vn30 = 1 if symbol in VN30_TICKERS else 0
            
            # Update trực tiếp vào cột is_vn30 (db_manager chưa hỗ trợ sẵn cột này qua upsert)
            conn = get_connection()
            conn.execute("UPDATE tickers SET is_vn30 = ? WHERE symbol = ?", (is_vn30, symbol))
            conn.commit()
            conn.close()
            
            count += 1
            if count % 100 == 0:
                print(f"Đã xử lý {count} mã...")
                
        except Exception as e:
            continue

    print(f"\n🎉 Đã nạp thành công {count} mã cổ phiếu vào database, bao gồm danh mục VN30!")

if __name__ == "__main__":
    seed_tickers()
